# Device-specific source boot images

Place the **original, unmodified** `boot.img` from the **same ROM/build and device** in this folder with one of these exact names:

| Selected device | Source filename |
| --- | --- |
| `selene` | `selene_boot.img` |
| `lancelot` | `lancelot_boot.img` |
| `merlin` | `merlin_boot.img` |

The Actions workflow picks `boot_img/${DEVICE}_boot.img` automatically after a successful build, replaces only the kernel with the freshly built one, and uploads a `boot.img` artifact. The result is padded to **64 MiB for selene**; for lancelot/merlin it retains the provided source image size because their partition limits have not been verified. It verifies the original ramdisk, DTB, boot header settings and other extracted components are preserved. If the selected image is absent, the kernel and AnyKernel3 artifacts are still built; only the boot.img export is skipped.

Use the original Boot image from the **exact same ROM and intended device**. Do **not** upload a recovery image or a boot image from another device or ROM. Repacked images are **not AVB-signed**: ensure your bootloader/verified boot setup supports custom boot images and retain a known-good boot image for recovery.

GitHub web UI only accepts files up to **25 MiB**. For a 64 MiB source use `git add`, `git commit`, `git push` or GitHub Desktop (Git push supports up to 100 MiB per file).