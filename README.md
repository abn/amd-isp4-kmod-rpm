# akmod-amd-isp4

[![Copr Build Status](https://copr.fedorainfracloud.org/coprs/abn/amd-isp4-kmod/package/amd-isp4-kmod/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/abn/amd-isp4-kmod/package/amd-isp4-kmod/)

Fedora **akmod** package for the AMD ISP4 camera driver, enabling the built-in camera on AMD Ryzen AI Max (Strix Halo) platforms.

The driver source is integrated via git submodules from [idovitz/amdisp4](https://github.com/idovitz/amdisp4).

## Installation

This driver is available via the [abn/amd-isp4-kmod](https://copr.fedorainfracloud.org/coprs/abn/amd-isp4-kmod/) Copr repository.

```bash
# Enable the Copr repository
sudo dnf copr enable abn/amd-isp4-kmod

# Install the akmod and meta-package
sudo dnf install akmod-amd-isp4 kmod-amd-isp4
```

### Secure Boot Enrollment (Required if Secure Boot is ON)

If your system has Secure Boot enabled, you **must** enroll a signing key so the kernel can trust and load the locally-compiled module.

1.  **Generate a signing key** (if you haven't already):
    ```bash
    sudo kmodgenca -a
    ```

2.  **Import the key into the MOK (Machine Owner Key) database**:
    ```bash
    sudo mokutil --import /etc/pki/akmods/certs/public_key.der
    ```
    *You will be prompted to enter a one-time password. You will need this after rebooting.*

3.  **Reboot your system.**
    During startup, you will see a blue screen ("Perform MOK Management"). Select **Enroll MOK**, then **Continue**, and **Yes** to confirm. Enter the password you chose in step 2.

4.  **Rebuild and load the module**:
    Once back in Fedora, force a rebuild to sign the module with your new key:
    ```bash
    sudo akmods --force --akmod amd-isp4-kmod
    sudo modprobe amd_isp4_capture
    ```

## Post-Installation

The module is compiled for your running kernel automatically. This typically takes about a minute. The `akmod` system ensures the driver is rebuilt automatically every time your kernel updates.

To verify the module is loaded:
```bash
lsmod | grep amd_isp4_capture
```

## Troubleshooting

If the module fails to load:

1.  **Check the akmods build log**:
    ```bash
    cat /var/cache/akmods/amd-isp4/*.log
    ```

2.  **Verify signature status**:
    ```bash
    modinfo amd_isp4_capture | grep signature
    ```
    If no signature is present or if `modprobe` reports "Key was rejected by service", ensure you have followed the Secure Boot steps above.

## Development

This project uses [tito](https://github.com/rpm-software-management/tito) for versioning and release management.

### Building RPMs locally

To perform a test build of the RPMs:
```bash
tito build --rpm --test
```

### Releasing to COPR

To tag a new version and release to COPR:
```bash
# Tag a new release (updates spec and creates git tag)
tito tag

# Release to COPR (as configured in .tito/releasers.conf)
tito release copr
```
