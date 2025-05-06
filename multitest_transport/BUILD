load("//third_party/bazel_rules/rules_shell/shell:sh_binary.bzl", "sh_binary")
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_appengine_binary", "pytype_strict_library", "third_party")
load("//tools/build_defs/license:license.bzl", "license")
load("//tools/build_defs/packaging:genzip.bzl", "genzip")
load("//tools/build_defs/packaging:pkg_library.bzl", "pkg_library")

# Android testing lab software for Android device partners
load("//tools/build_defs/testing:bzl_library.bzl", "bzl_library")

package(
    default_applicable_licenses = ["//multitest_transport:license"],
    default_visibility = [":multitest_transport"],
)

license(
    name = "license",
    package_name = "multitest_transport",
)

licenses(["notice"])

exports_files(["LICENSE"])

package_group(
    name = "multitest_transport",
    packages = [
        "//multitest_transport/...",
        "@tradefed_cluster//tradefed_cluster/...",
    ],
)

exports_files(["serve.sh"])

filegroup(
    name = "prebuilts",
    srcs = glob(
        [
            "prebuilts/**",
        ],
        exclude = [
            "prebuilts/tools/README.md",
            "prebuilts/deviceinfra/**",
        ],
    ),
)

config_setting(
    name = "dev_mode",
    define_values = {
        "dev_mode": "true",
    },
)

py_appengine_binary(
    name = "main",
    configs = [
        "config.yaml",
        "sitecustomize.py",
        "//multitest_transport/gae_configs",
    ],
    data = select({
        ":dev_mode": [],
        "//conditions:default": ["Dockerfile"],
    }) + [
        ":prebuilts",
        ":serve.sh",
        "//multitest_transport/file_cleaner:file_cleaner_lib",
        "//multitest_transport/file_server:file_server_lib",
        "//multitest_transport/scripts",
    ],
    deps = [
        ":server_lib",
        "//multitest_transport/app_helper:launcher_lib",
        "//multitest_transport/app_helper:rabbitmq_plugin_lib",
        "//multitest_transport/app_helper:rabbitmq_puller_lib",
        "//multitest_transport/plugins",
        "@tradefed_cluster//tradefed_cluster:app_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("pymysql"),
    ],
)

# To run the server locally, use:
# $ iblaze run mtt_server
# To run the server with javascript recompiling on page refresh, use:
# $ iblaze run mtt_server --define dev_mode=true
# Additional arguments can be added as -- --param_name param_value, e.g.:
# $ iblaze run mtt_server --define dev_mode=true -- --storage_path /tmp/mtt
sh_binary(
    name = "mtt_server",
    srcs = [":serve.sh"],
    args = select({
        "dev_mode": [
            "--dev_mode true",
            "--live_reload true",
        ],
        "//conditions:default": [],
    }) + [
        "--working_dir '..'",
    ],
    data = [
        ":main",
    ],
)

pytype_strict_library(
    name = "server_lib",
    srcs = [
        "server.py",
    ],
    deps = [
        "//multitest_transport/api",
        "//multitest_transport/build_manager:xts_requirements_detector_lib",
        "//multitest_transport/core:app_lib",
        "//multitest_transport/core:cron_kicker_lib",
        "//multitest_transport/file_server:proxy_lib",
        "//multitest_transport/sidekicks",
        "//multitest_transport/test_scheduler",
        "//multitest_transport/test_scheduler:test_kicker_lib",
        "//multitest_transport/test_scheduler:test_plan_kicker_lib",
        "//multitest_transport/test_scheduler:tfc_event_handler_lib",
        "//multitest_transport/tools/webaoa",
        "//multitest_transport/ui2",
        "//multitest_transport/util:analytics_uploader_lib",
        "@tradefed_cluster//tradefed_cluster:server_lib",
        "@tradefed_cluster//tradefed_cluster/services:task_scheduler_lib",
    ],
)


bzl_library(
    name = "adapter_bzl",
    srcs = ["adapter.bzl"],
    parse_tests = False,
    visibility = ["//visibility:private"],
)

bzl_library(
    name = "adapter.bazel_bzl",
    srcs = ["adapter.bazel.bzl"],
    parse_tests = False,
    visibility = ["//visibility:private"],
)
