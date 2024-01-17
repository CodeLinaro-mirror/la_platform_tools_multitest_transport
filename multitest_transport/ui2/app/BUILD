# MTT application root
load("//multitest_transport:adapter.bzl", "ng_module", "sass_binary", "sass_library", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

# Material theme and styling
sass_library(
    name = "app_styles_lib",
    srcs = ["app.scss"],
    strict_deps = False,
    visibility = ["//multitest_transport"],
    deps = ["//multitest_transport/ui2:constants"],
)

sass_binary(
    name = "app_styles",
    src = "app.scss",
    output_name = "app.css",
    sass_stack = False,
    strict_deps = False,
    deps = [":app_styles_lib"],
)

ng_module(
    name = "app",
    srcs = ["app.ts"],
    allow_warnings = True,
    assets = [
        "app.ng.html",
        ":app_styles",
    ],
    slow_development_build = True,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular2:common_http"),
        third_party_js("angular2:core"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("angular_components:material_tooltip"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/auth",
        "//multitest_transport/ui2/app/build_channels",
        "//multitest_transport/ui2/app/builds",
        "//multitest_transport/ui2/app/config_sets",
        "//multitest_transport/ui2/app/device_actions",
        "//multitest_transport/ui2/app/devices",
        "//multitest_transport/ui2/app/file_browser",
        "//multitest_transport/ui2/app/file_cleaner",
        "//multitest_transport/ui2/app/hosts",
        "//multitest_transport/ui2/app/notes",
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/settings",
        "//multitest_transport/ui2/app/setup_wizard",
        "//multitest_transport/ui2/app/shared",
        "//multitest_transport/ui2/app/test_plans",
        "//multitest_transport/ui2/app/test_run_actions",
        "//multitest_transport/ui2/app/test_runs",
        "//multitest_transport/ui2/app/tests",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = ["app_test.ts"],
    visibility = ["//multitest_transport"],
    deps = [
        ":app",
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:router_testing"),
        third_party_js("typings/jasmine"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/testing:jasmine_util",
    ],
)
