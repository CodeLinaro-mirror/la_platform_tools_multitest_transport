# Frontend application for MTT

load("//multitest_transport:adapter.bzl", "COMPILER_FLAGS", "js_binary", "karma_web_test_suite", "ng_module", "sass_binary", "sass_library", "third_party_js", "ts_config", "ts_development_sources")
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "Fileset", "FilesetEntry", "pytype_strict_library", "third_party")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

# Main Angular module
ng_module(
    name = "app_lib",
    srcs = [
        "main.ts",
    ],
    assets = [
        "index.html",
    ],
    deps = [
        third_party_js("angular2:core"),
        third_party_js("angular2:platform_browser"),
        "//multitest_transport/ui2/app",
    ],
)

################################################################################
# Styles                                                                       #
################################################################################

# Sass constants
sass_library(
    name = "constants",
    srcs = ["_constants.scss"],
    visibility = ["//multitest_transport"],
)

# shared styles for mtt lab
sass_library(
    name = "styles_lib",
    srcs = ["styles.scss"],
    visibility = ["//multitest_transport"],
    deps = [
        ":constants",
    ],
)

# Material theme and styling
sass_binary(
    name = "styles",
    src = "styles.scss",
    output_name = "styles.css",
    sass_stack = False,
    visibility = ["//multitest_transport"],
    deps = [
        ":constants",
    ],
)

################################################################################
# Static files                                                                 #
################################################################################

Fileset(
    name = "static_files",
    out = "static",
    entries = [
        FilesetEntry(
            files = [":styles"],
            destdir = "css",
        ),
        FilesetEntry(
            files = glob(["images/*"]),
        ),
    ],
)

################################################################################
# Development mode                                                             #
################################################################################

ts_development_sources(
    name = "dev_sources",
    runtime_deps = [
        third_party_js("moment"),
        third_party_js("moment_duration_format"),
    ],
    deps = [
        ":app_lib",
    ],
)

################################################################################
# Production mode                                                              #
################################################################################

THIRD_PARTY_JS = [
    third_party_js("moment:moment_minified"),
    third_party_js("moment_duration_format"),
]

# Compiled production binary
js_binary(
    name = "compiled",
    defs = COMPILER_FLAGS,
    externs_list = [
        "//third_party/javascript/moment:externs",
    ],
    use_precompiled_libraries = False,
    deps = [
        ":app_lib",
    ],
)

js_binary(
    name = "uncompiled",
    compile = False,
    deps = THIRD_PARTY_JS,
)

genrule(
    name = "app",
    srcs = [
        ":uncompiled-bundle.js",
        ":compiled.js",
    ],
    outs = ["app.js"],
    cmd = "cat $(SRCS) > $@",
)

# Development mode flag
config_setting(
    name = "dev_mode",
    define_values = {
        "dev_mode": "true",
    },
)

# Python server
pytype_strict_library(
    name = "ui2",
    srcs = [
        "main.py",
    ],
    data = [
        "index.html",
        ":static_files",
    ] + select({
        ":dev_mode": [":dev_sources.concat.js"],
        "//conditions:default": ["app.js"],
    }),
    visibility = ["//multitest_transport"],
    deps = [
        "//multitest_transport/models",
        "//multitest_transport/util",
        third_party("flask"),
    ],
)

ts_development_sources(
    name = "dev_sources_for_testing",
    testonly = 1,
    runtime_deps = THIRD_PARTY_JS + [
        "//multitest_transport/ui2/app/testing:init_tests",
    ],
    deps = [
        "//multitest_transport/ui2/app:tests",
        "//multitest_transport/ui2/app/auth:tests",
        "//multitest_transport/ui2/app/build_channels:tests",
        "//multitest_transport/ui2/app/builds:tests",
        "//multitest_transport/ui2/app/config_sets:tests",
        "//multitest_transport/ui2/app/device_actions:tests",
        "//multitest_transport/ui2/app/devices:tests",
        "//multitest_transport/ui2/app/file_browser:tests",
        "//multitest_transport/ui2/app/file_cleaner:tests",
        "//multitest_transport/ui2/app/hosts:tests",
        "//multitest_transport/ui2/app/notes:tests",
        "//multitest_transport/ui2/app/recovery:tests",
        "//multitest_transport/ui2/app/services:tests",
        "//multitest_transport/ui2/app/settings:tests",
        "//multitest_transport/ui2/app/setup_wizard:tests",
        "//multitest_transport/ui2/app/shared:tests",
        "//multitest_transport/ui2/app/test_plans:tests",
        "//multitest_transport/ui2/app/test_run_actions:tests",
        "//multitest_transport/ui2/app/test_runs:tests",
        "//multitest_transport/ui2/app/tests:tests_",
    ],
)

# TypeScript IDE configuration
ts_config(
    name = "tsconfig",
    deps = [
        ":app_lib",
        "//multitest_transport/ui2/app:tests",
        "//multitest_transport/ui2/app/auth:tests",
        "//multitest_transport/ui2/app/build_channels:tests",
        "//multitest_transport/ui2/app/builds:tests",
        "//multitest_transport/ui2/app/config_sets:tests",
        "//multitest_transport/ui2/app/device_actions:tests",
        "//multitest_transport/ui2/app/devices:tests",
        "//multitest_transport/ui2/app/file_browser:tests",
        "//multitest_transport/ui2/app/file_cleaner:tests",
        "//multitest_transport/ui2/app/hosts:tests",
        "//multitest_transport/ui2/app/notes:tests",
        "//multitest_transport/ui2/app/recovery:tests",
        "//multitest_transport/ui2/app/services:tests",
        "//multitest_transport/ui2/app/settings:tests",
        "//multitest_transport/ui2/app/setup_wizard:tests",
        "//multitest_transport/ui2/app/shared:tests",
        "//multitest_transport/ui2/app/test_plans:tests",
        "//multitest_transport/ui2/app/test_run_actions:tests",
        "//multitest_transport/ui2/app/test_runs:tests",
        "//multitest_transport/ui2/app/tests:tests_",
    ],
)

karma_web_test_suite(
    name = "unit_tests",
    browsers = [
        "//testing/web/browsers:chrome-linux",
    ],
    data = [
        "styles.css",
        "tsconfig",
    ],
    manifest = ":dev_sources_for_testing",
    shard_count = 10,
)

