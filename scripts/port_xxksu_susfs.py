#!/usr/bin/env python3
"""Bridge xxKSU (backslashxx) to Zenith in-tree SuSFS 2.3.0 on legacy 4.14.

Only patches the temporary GitHub Actions checkout. Every upstream anchor
must occur exactly once; unexpected revisions fail before kernel compilation.
"""
from pathlib import Path
import sys

from port_ksun_susfs import patch, SUSFS_SUPERCALLS


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: port_xxksu_susfs.py <kernel source directory>")
    source = Path(sys.argv[1]).resolve()
    ksu = source / "drivers" / "kernelsu"
    for path in ("fs/susfs.c", "fs/susfs/Kconfig", "include/linux/susfs.h",
                 "include/linux/susfs_def.h"):
        if not (source / path).is_file():
            raise RuntimeError(f"Missing Zenith SuSFS file: {path}")
    if not (ksu / "ksu.c").is_file() or not (ksu / "supercall/supercall.c").is_file():
        raise RuntimeError("Expected pinned backslashxx/KernelSU unity layout")

    patch(ksu, "ksu.c",
          '#include "kernel_includes.h"\n',
          '#include "kernel_includes.h"\n'
          '#ifdef CONFIG_KSU_SUSFS\n'
          '#include <linux/susfs.h>\n'
          '#endif\n')
    patch(ksu, "ksu.c",
          '\tksu_core_init();\n',
          '\tksu_core_init();\n'
          '#ifdef CONFIG_KSU_SUSFS\n'
          '\tsusfs_init();\n'
          '#endif\n')

    patch(ksu, "selinux/selinux.c",
          'u32 ksu_file_sid __read_mostly = 0;\n',
          'u32 ksu_file_sid __read_mostly = 0;\n'
          '#ifdef CONFIG_KSU_SUSFS\n'
          'u32 susfs_ksu_sid __read_mostly = 0;\n'
          'u32 susfs_priv_app_sid __read_mostly = 0;\n'
          '#endif\n')
    patch(ksu, "selinux/selinux.c",
          '\terr = security_secctx_to_secid(ZYGOTE_CONTEXT, strlen(ZYGOTE_CONTEXT), &cached_zygote_sid);\n',
          '#ifdef CONFIG_KSU_SUSFS\n'
          '\tsusfs_ksu_sid = cached_su_sid;\n'
          '\tif (security_secctx_to_secid("u:r:priv_app:s0:c512,c768",\n'
          '\t                             strlen("u:r:priv_app:s0:c512,c768"),\n'
          '\t                             &susfs_priv_app_sid))\n'
          '\t\tsusfs_priv_app_sid = 0;\n'
          '#endif\n'
          '\terr = security_secctx_to_secid(ZYGOTE_CONTEXT, strlen(ZYGOTE_CONTEXT), &cached_zygote_sid);\n')
    patch(ksu, "selinux/selinux.c",
          'bool is_ksu_domain(void)\n',
          '#ifdef CONFIG_KSU_SUSFS\n'
          'bool susfs_is_current_ksu_domain(void)\n'
          '{\n\treturn is_task_ksu_domain(current_cred());\n}\n'
          '#endif\n\nbool is_ksu_domain(void)\n')

    patch(ksu, "supercall/supercall.c",
          '#define KSU_DRIVER_PERMISSION_SU_SESSION (1UL << 0)\n',
          '#define KSU_DRIVER_PERMISSION_SU_SESSION (1UL << 0)\n'
          '#ifdef CONFIG_KSU_SUSFS\n'
          '#include <linux/susfs.h>\n'
          '#include <linux/susfs_def.h>\n'
          '#endif\n')
    patch(ksu, "supercall/supercall.c",
          '\tif (magic1 != KSU_INSTALL_MAGIC1)\n\t\treturn 0;\n',
          '\tif (magic1 != KSU_INSTALL_MAGIC1)\n\t\treturn 0;\n' + SUSFS_SUPERCALLS)

    patch(ksu, "hook/setuid_hook.c",
          '\tksu_handle_umount(new, old);\n\treturn;\n',
          '\tksu_handle_umount(new, old);\n'
          '#ifdef CONFIG_KSU_SUSFS\n'
          '\t/* Match the non-SU-app unmount visibility of the original SuSFS bridge. */\n'
          '\tif (is_zygote(old) &&\n'
          '\t    (is_appuid(new_uid) || is_isolated_process(new_uid)) &&\n'
          '\t    (ksu_uid_should_umount(new_uid) || is_isolated_process(new_uid))) {\n'
          '\t\tsusfs_set_current_proc_umounted();\n'
          '#ifdef CONFIG_KSU_SUSFS_SUS_PATH\n'
          '\t\tschedule_work(&susfs_extra_works);\n'
          '#endif\n'
          '\t}\n'
          '#endif\n\treturn;\n')

    patch(ksu, "runtime/boot_event.c",
          '\ttrack_throne(true);\n',
          '\ttrack_throne(true);\n'
          '#ifdef CONFIG_KSU_SUSFS\n'
          '\tsusfs_start_sdcard_monitor_fn();\n'
          '#endif\n')
    print("xxKSU: Zenith SuSFS 2.3.0 bridge installed in temporary checkout")


if __name__ == "__main__":
    main()
