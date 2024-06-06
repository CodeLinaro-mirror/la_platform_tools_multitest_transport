load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

# Material theme and styling
per_file_sass_binaries(
    name = "styles",
    srcs = glob(["*.scss"]),
    deps = ["//multitest_transport/ui2:constants"],
)

ng_module(
    name = "test_plans",
    srcs = [
        "test_plan_edit_page.ts",
        "test_plan_list.ts",
        "test_plan_list_page.ts",
        "test_plans_module.ts",
    ],
    assets = [
        ":styles",
        "test_plan_edit_page.ng.html",
        "test_plan_list_page.ng.html",
        "test_plan_list.ng.html",
    ],
    strict_templates = False,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular2:core"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:router"),
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:cdk_keycodes"),
        third_party_js("angular_components:material_button"),
        third_party_js("angular_components:material_chips"),
        third_party_js("angular_components:material_stepper"),
        third_party_js("angular_components:material_table"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/build_channels",
        "//multitest_transport/ui2/app/device_actions",
        "//multitest_transport/ui2/app/devices",
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
        "//multitest_transport/ui2/app/test_run_actions",
        "//multitest_transport/ui2/app/test_runs",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "test_plan_edit_page_test.ts",
        "test_plan_list_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":test_plans",
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:material_chips"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/testing:jasmine_util",
        "//multitest_transport/ui2/app/testing:test_util",
    ],
)
