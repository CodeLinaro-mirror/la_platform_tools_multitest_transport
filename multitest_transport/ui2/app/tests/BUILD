# Angular components for MTT test pages.
load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

licenses(["notice"])

package(
    default_applicable_licenses = ["//multitest_transport:license"],
    default_visibility = ["//multitest_transport"],
)

per_file_sass_binaries(
    name = "styles",
    srcs = glob(["*.scss"]),
    deps = ["//multitest_transport/ui2:constants"],
)

ng_module(
    name = "tests",
    srcs = [
        "test_edit_page.ts",
        "test_list.ts",
        "test_list_page.ts",
        "test_module.ts",
    ],
    assets = [
        ":styles",
        "test_edit_page.ng.html",
        "test_list.ng.html",
        "test_list_page.ng.html",
    ],
    strict_templates = False,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular2:core"),
        third_party_js("angular2:forms"),
        third_party_js("angular_components:material_button"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:router"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/build_channels",
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
    ],
)

ng_module(
    name = "tests_",
    testonly = True,
    srcs = [
        "test_edit_page_test.ts",
        "test_list_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":tests",
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular2:router_testing"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/testing:jasmine_util",
        "//multitest_transport/ui2/app/testing:test_util",
    ],
)
