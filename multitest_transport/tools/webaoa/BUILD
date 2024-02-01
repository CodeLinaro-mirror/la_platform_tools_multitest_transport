# WebAOA tool
load("//multitest_transport:adapter.bzl", "COMPILER_FLAGS", "js_binary", "karma_web_test_suite", "ng_module", "sass_binary", "third_party_js", "ts_config", "ts_development_sources")
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "pytype_strict_library", "third_party")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

# Angular application
ng_module(
    name = "app_lib",
    srcs = [
        "main.ts",
    ],
    deps = [
        ":app_ng",
        third_party_js("angular2:core"),
        third_party_js("angular2:platform_browser"),
    ],
)

# Angular module styling
sass_binary(
    name = "app_style",
    src = "app.scss",
)

# Angular module
ng_module(
    name = "app_ng",
    srcs = [
        "app.ts",
        "app_module.ts",
    ],
    assets = [
        ":app_style",
        "app.ng.html",
        "index.html",
    ],
    deps = [
        "//multitest_transport/tools/webaoa/device",
        "//multitest_transport/tools/webaoa/editor",
        third_party_js("angular2:core"),
        third_party_js("angular_components:material_icon"),
        third_party_js("angular_components:material_button"),
        third_party_js("angular_components:material_tooltip"),
        third_party_js("angular_components:material_toolbar"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:platform_browser_animations"),
    ],
)

# Angular module tests
ng_module(
    name = "app_tests",
    testonly = True,
    srcs = ["app_test.ts"],
    deps = [
        ":app_ng",
        "//multitest_transport/tools/webaoa/device",
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:platform_browser"),
        "//multitest_transport/ui2/app/testing:jasmine_util",
    ],
)

# Development sources
ts_development_sources(
    name = "dev_sources",
    deps = [
        ":app_lib",
        ":app_ng",
    ],
)

# TypeScript IDE configuration
ts_config(
    name = "tsconfig",
    deps = [
        ":app_lib",
        ":app_ng",
        ":app_tests",
        "//multitest_transport/tools/webaoa/device:tests",
        "//multitest_transport/tools/webaoa/editor:tests",
    ],
)

# Test sources
ts_development_sources(
    name = "test_sources",
    testonly = True,
    runtime_deps = [
        "//multitest_transport/ui2/app/testing:init_tests",
    ],
    deps = [
        ":app_tests",
        "//multitest_transport/tools/webaoa/device:tests",
        "//multitest_transport/tools/webaoa/editor:tests",
    ],
)

# Unit tests
karma_web_test_suite(
    name = "unit_tests",
    browsers = ["//testing/web/browsers:chrome-linux"],
    data = [":tsconfig"],
    manifest = ":test_sources",
)

# Styling
sass_binary(
    name = "styles",
    src = "styles.scss",
    deps = [
        third_party_js("angular_components:material_sass"),
        third_party_js("angular_components:deprecated_sass"),
    ],
)

# Production binary
js_binary(
    name = "compiled",
    defs = COMPILER_FLAGS,
    deps = [":app_lib"],
)

# Static files
Fileset(
    name = "static_fs",
    out = "static",
    entries = [
        FilesetEntry(
            files = [
                "device.png",
                "favicon.ico",
                ":styles",
            ],
        ),
    ],
)

# Development mode flag
config_setting(
    name = "dev_mode",
    define_values = {
        "dev_mode": "true",
    },
)

# WSGI server
pytype_strict_library(
    name = "webaoa",
    srcs = [
        "server.py",
    ],
    data = [
        "index.html",
        ":static_fs",
    ] + select({
        ":dev_mode": [":dev_sources.concat.js"],
        "//conditions:default": [":compiled"],
    }),
    visibility = ["//multitest_transport"],
    deps = [
        third_party("flask"),
        "//multitest_transport/models",
        "//multitest_transport/util",
    ],
)
