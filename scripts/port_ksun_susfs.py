#!/usr/bin/env python3
"""Integrate Zenith's in-tree SuSFS with pinned official KernelSU-Next legacy.

Patch only the temporary checkout used by GitHub Actions. Every anchor must
match exactly; fail closed if an upstream refactor changes the interface.
"""
from pathlib import Path
import sys


def patch(ksu, file, before, after):
    path = ksu / file
    content = path.read_text()
    n = content.count(before)
    if n != 1:
        raise RuntimeError(f"{file}: expected one patch anchor, found {n}: {before[:80]!r}")
    path.write_text(content.replace(before, after, 1))


SUSFS_SUPERCALLS = """
#ifdef CONFIG_KSU_SUSFS
    /* SuSFS non-GKI reboot API; only UID 0 can send these commands. */
    if (magic2 == SUSFS_MAGIC && current_uid().val == 0) {
        switch (cmd) {
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
        case CMD_SUSFS_ADD_SUS_PATH:
            susfs_add_sus_path(arg);
            break;
        case CMD_SUSFS_ADD_SUS_PATH_LOOP:
            susfs_add_sus_path_loop(arg);
            break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
        case CMD_SUSFS_HIDE_SUS_MNTS_FOR_NON_SU_PROCS:
            susfs_set_hide_sus_mnts_for_non_su_procs(arg);
            break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
        case CMD_SUSFS_ADD_SUS_KSTAT:
        case CMD_SUSFS_ADD_SUS_KSTAT_STATICALLY:
            susfs_add_sus_kstat(arg);
            break;
        case CMD_SUSFS_UPDATE_SUS_KSTAT:
            susfs_update_sus_kstat(arg);
            break;
#endif
#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
        case CMD_SUSFS_ADD_TRY_UMOUNT:
            susfs_add_try_umount(arg);
            break;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
        case CMD_SUSFS_SET_UNAME:
            susfs_set_uname(arg);
            break;
#endif
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
        case CMD_SUSFS_ENABLE_LOG:
            susfs_enable_log(arg);
            break;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
        case CMD_SUSFS_SET_CMDLINE_OR_BOOTCONFIG:
            susfs_set_cmdline_or_bootconfig(arg);
            break;
#endif
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
        case CMD_SUSFS_ADD_OPEN_REDIRECT:
            susfs_add_open_redirect(arg);
            break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MAP
        case CMD_SUSFS_ADD_SUS_MAP:
            susfs_add_sus_map(arg);
            break;
#endif
        case CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING:
            susfs_set_avc_log_spoofing(arg);
            break;
        case CMD_SUSFS_SHOW_ENABLED_FEATURES:
            susfs_get_enabled_features(arg);
            break;
        case CMD_SUSFS_SHOW_VARIANT:
            susfs_show_variant(arg);
            break;
        case CMD_SUSFS_SHOW_VERSION:
            susfs_show_version(arg);
            break;
        default:
            break;
        }
        return 0;
    }
#endif
"""


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: port_ksun_susfs.py <kernel source directory>")
    source = Path(sys.argv[1]).resolve()
    ksu = source / "drivers" / "kernelsu"
    for path in ("fs/susfs.c", "fs/susfs/Kconfig", "include/linux/susfs.h"):
        if not (source / path).is_file():
            raise RuntimeError(f"Missing Zenith in-tree SuSFS file: {path}")
    if not (ksu / "core/init.c").is_file():
        raise RuntimeError("Expected official KernelSU-Next legacy layout")

    patch(ksu, "core/init.c",
          '#include "feature/adb_root.h"\n',
          '#include "feature/adb_root.h"\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs.h>\n#endif\n')
    patch(ksu, "core/init.c",
          '\tksu_lsm_hook_init();\n',
          '\tksu_lsm_hook_init();\n#ifdef CONFIG_KSU_SUSFS\n\tsusfs_init();\n#endif\n')
    patch(ksu, "selinux/selinux.c",
          'bool is_ksu_domain(void)\n',
          '#ifdef CONFIG_KSU_SUSFS\n'
          'bool susfs_is_current_ksu_domain(void)\n'
          '{\n\treturn is_task_ksu_domain(current_cred());\n}\n'
          '#endif\n\nbool is_ksu_domain(void)\n')
    patch(ksu, "supercall/supercall.c",
          '#include <linux/utsname.h> // utsname() and uts_sem\n',
          '#include <linux/utsname.h> // utsname() and uts_sem\n'
          '#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs.h>\n#include <linux/susfs_def.h>\n#endif\n')
    patch(ksu, "supercall/supercall.c",
          '\tif (magic1 != KSU_INSTALL_MAGIC1)\n\t\treturn 0;\n',
          '\tif (magic1 != KSU_INSTALL_MAGIC1)\n\t\treturn 0;\n' + SUSFS_SUPERCALLS)
    patch(ksu, "hook/setuid_hook.c",
          '#include "compat/kernel_compat.h"\n',
          '#include "compat/kernel_compat.h"\n'
          '#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs_def.h>\n'
          '#include <linux/workqueue.h>\n#include "ksu.h"\n'
          '#include "selinux/selinux.h"\n'
          'extern struct work_struct susfs_extra_works;\n#endif\n')
    patch(ksu, "hook/setuid_hook.c",
          '    ksu_handle_umount(old_uid, new_uid);\n',
          '    ksu_handle_umount(old_uid, new_uid);\n'
          '#ifdef CONFIG_KSU_SUSFS\n'
          '    /* Do not change upstream root/umount permission decisions. */\n'
          '    if (is_zygote(current_cred()) &&\n'
          '        (is_appuid(new_uid) || is_isolated_process(new_uid)) &&\n'
          '        (ksu_uid_should_umount(new_uid) || is_isolated_process(new_uid))) {\n'
          '        susfs_set_current_proc_umounted();\n'
          '#ifdef CONFIG_KSU_SUSFS_SUS_PATH\n'
          '        schedule_work(&susfs_extra_works);\n'
          '#endif\n'
          '    }\n'
          '#endif\n')
    patch(ksu, "runtime/boot_event.c",
          '#include "feature/selinux_hide.h"\n',
          '#include "feature/selinux_hide.h"\n#ifdef CONFIG_KSU_SUSFS\n'
          '#include <linux/susfs.h>\n#endif\n')
    patch(ksu, "runtime/boot_event.c",
          '    ksu_avc_spoof_late_init();\n',
          '    ksu_avc_spoof_late_init();\n#ifdef CONFIG_KSU_SUSFS\n'
          '    susfs_start_sdcard_monitor_fn();\n#endif\n')
    print("Official KernelSU-Next legacy: Zenith SuSFS hooks installed")


if __name__ == "__main__":
    main()
