load("//tools/build_defs/packaging:genzip.bzl", "genzip")
load("//tools/build_defs/packaging:pkg_library.bzl", "pkg_library")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

pkg_library(
    name = "juicefs",
    srcs = [
        ".env",
        "README.md",
        "docker-compose.jfs.yml",
        "entrypoint.sh",
        "jfs_client.sh",
        "jfs_service.sh",
    ],
    package_dir = "juicefs",
)

genzip(
    name = "juicefs.zip",
    deps = [":juicefs"],
)
