%global debug_package %{nil}
%global kmod_name     amd-isp4
# Pre-define naming macros with literal values so the main package header
# resolves even in limited parse contexts (e.g. dnf builddep).
# kmodtool will redefine these to the same values inside its fedora guard.
%global kmod_pkg_name kmod-amd-isp4
%global pkg_kmod_name amd-isp4-kmod

# akmods defines 'kernels' but our spec uses 'for_kernels' (from kmodtool convention).
# Map them if 'kernels' is present.
%{?kernels:%global for_kernels %{kernels}}

# ── Main package header (must precede any %%package directives) ──────────────
Name:           %{pkg_kmod_name}
Version:        8
Release:        1%{?dist}
Summary:        Kernel module source for AMD ISP4 Ryzen AI Max Camera
License:        GPL-2.0-or-later
URL:            https://github.com/idovitz/amdisp4
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  kmodtool
BuildRequires:  elfutils-libelf-devel
BuildRequires:  patch
%if 0%{?for_kernels:1}
BuildRequires:  kernel-devel
%endif

# ── Per-kernel kmod subpackage (akmods rebuild path only) ────────────────────
# kmodtool generates the kmod-amd-isp4-<kver> package definition and %files
# when akmods rebuilds with: rpmbuild --rebuild --define "for_kernels <kver>"
%if 0%{?for_kernels:1}
%{expand:%(kmodtool --target %{_target_cpu} --kmodname %{kmod_name} --for-kernels "%{for_kernels}" 2>/dev/null)}
%endif

# ── Akmod subpackage (distribution build only) ───────────────────────────────
# Defined manually (not via kmodtool --akmod) so we can add
# Provides: amd-isp4-kmod-common, which kmodtool injects as a Requires into
# both the akmod and per-kernel kmod packages. This driver has no separate
# common files (firmware, udev rules), so the akmod package self-provides it.
%if ! 0%{?for_kernels:1}
%package -n akmod-%{kmod_name}
Summary:        Akmod package for the AMD ISP4 camera driver
Requires:       akmods
Requires:       kmodtool
Provides:       %{pkg_kmod_name} = %{version}-%{release}
Provides:       %{pkg_kmod_name}-common >= %{version}

%description -n akmod-%{kmod_name}
This akmod package for the AMD ISP4 camera driver ensures the kernel module
(amd_isp4_capture.ko) is rebuilt automatically for every new kernel update
by the akmods service.

%posttrans -n akmod-%{kmod_name}
nohup /usr/sbin/akmods --from-akmod-posttrans --akmod %{kmod_name} &>/dev/null &

%post -n akmod-%{kmod_name}
[ -x /usr/sbin/akmods-ostree-post ] && \
    /usr/sbin/akmods-ostree-post %{kmod_name} \
    %{_usrsrc}/akmods/%{pkg_kmod_name}-%{version}-%{release}.src.rpm

# ── Meta package ─────────────────────────────────────────────────────────────
%package -n %{kmod_pkg_name}
Summary:        Metapackage tracking the AMD ISP4 kernel module for the newest kernel
Provides:       %{pkg_kmod_name} = %{version}-%{release}
Requires:       akmod-%{kmod_name} = %{version}-%{release}

%description -n %{kmod_pkg_name}
This is a meta-package whose sole purpose is to require akmod-%{kmod_name}.
Installing it ensures the AMD ISP4 kernel module is present and rebuilt
whenever the kernel changes.
%endif

# ── Main package description ─────────────────────────────────────────────────
%description
This package contains the kernel module for the AMD ISP4 camera driver,
providing video capture support for AMD Ryzen AI Max platforms.

%prep
# Extract contents directly into the build directory, stripping the top-level
# directory name which may vary (e.g. git hash vs version).
%setup -q -c -T
tar -xf %{SOURCE0} --strip-components=1

# Apply all patches to the submodule source.
# They are kernel-tree style (-p1 strips the a/b/ prefix)
# and create the driver source under drivers/media/platform/amd/isp4/
# The patches are located inside the submodule itself.
for p in amdisp4/patches/*.patch; do
    echo "Applying $p..."
    patch -p1 -d amdisp4 < "$p"
done

%build
%if 0%{?for_kernels:1}
# Abort if kmodtool failed to generate the per-kernel package template.
# %{?kmodtool_check} expands to empty on success (macro undefined) and to
# "echo ERROR; exit 1" on failure — safe to use in a scriptlet.
%{?kmodtool_check}
# Build the out-of-tree kernel module for each specified kernel.
# We use the in-tree Makefile at drivers/media/platform/amd/isp4/ directly,
# passing CONFIG_VIDEO_AMD_ISP4_CAPTURE=m so obj-$(CONFIG_...) becomes obj-m.
_srcdir=$(pwd)/amdisp4/drivers/media/platform/amd/isp4
for kernel in %{for_kernels}; do
    make -C %{_usrsrc}/kernels/${kernel} \
         M=${_srcdir} \
         CONFIG_VIDEO_AMD_ISP4_CAPTURE=m \
         modules
done
%endif

%install
%if 0%{?for_kernels:1}
# Install the compiled .ko for each kernel.
# kmodtool's %files for kmod-amd-isp4-<kver> expects modules at:
#   /lib/modules/<kver>/extra/amd-isp4/
# Module signing and compression are handled by kmodtool's
# %%global __spec_install_post override, not called explicitly here.
_srcdir=$(pwd)/amdisp4/drivers/media/platform/amd/isp4
for kernel in %{for_kernels}; do
    install -d %{buildroot}/lib/modules/${kernel}/extra/%{kmod_name}/
    install -m 644 ${_srcdir}/*.ko \
        %{buildroot}/lib/modules/${kernel}/extra/%{kmod_name}/
done
%else
# Build the akmod package: create an SRPM from this spec and install it to
# /usr/src/akmods/ so akmods can rebuild it for every future kernel.
#
# The spec file is available in the root of the extracted source tree.
mkdir -p %{_specdir}
install -m 644 %{name}.spec %{_specdir}/%{name}.spec
mkdir -p %{buildroot}/%{_usrsrc}/akmods/
# tito renames the tarball, so we ensure the expected filename is present
# for the nested rpmbuild to find it in _sourcedir.
cp %{SOURCE0} %{_sourcedir}/%{pkg_kmod_name}-%{version}.tar.gz
rpmbuild --define "_sourcedir %{_sourcedir}" \
         --define "_srcrpmdir %{buildroot}/%{_usrsrc}/akmods/" \
         %{?dist:--define "dist %{dist}"} \
         -bs --nodeps %{_specdir}/%{name}.spec
ln -sf "$(ls %{buildroot}/%{_usrsrc}/akmods/*.src.rpm | xargs basename)" \
    %{buildroot}/%{_usrsrc}/akmods/%{pkg_kmod_name}.latest
%endif

# ── Files ────────────────────────────────────────────────────────────────────
%if ! 0%{?for_kernels:1}
%files -n akmod-%{kmod_name}
%defattr(-,root,root,-)
%{_usrsrc}/akmods/

%files -n %{kmod_pkg_name}
# no files; this meta-package exists only to pull in the akmod package
%endif

%changelog
* Sun Feb 22 2026 Arun Babu Neelicattu <arun.neelicattu@gmail.com> 8-1
- new package built with tito
- add v8 of lkml patch series

