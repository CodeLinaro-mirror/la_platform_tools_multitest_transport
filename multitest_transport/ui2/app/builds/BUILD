load("//multitest_transport:adapter.bzl", "ng_module", "sass_binary", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

sass_binary(
    name = "build_create_page",
    src = "build_create_page.scss",
    output_name = "build_create_page.css",
    visibility = ["//multitest_transport"],
)

sass_binary(
    name = "build_list",
    src = "build_list.scss",
    output_name = "build_list.css",
    visibility = ["//multitest_transport"],
)

ng_module(
    name = "builds",
    srcs = [
        "build_create_page.ts",
        "build_list.ts",
        "build_list_page.ts",
        "builds_module.ts",
    ],
    assets = [
        ":build_create_page",
        ":build_list",
        "build_create_page.ng.html",
        "build_list.ng.html",
        "build_list_page.ng.html",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular2:core"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:router"),
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:cdk_keycodes"),
        third_party_js("angular_components:material_button"),
        third_party_js("angular_components:material_chips"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("angular_components:material_table"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "build_create_page_test.ts",
        "build_list_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":builds",
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router_testing"),
        third_party_js("angular_components:material_chips"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/testing:jasmine_util",
        "//multitest_transport/ui2/app/testing:test_util",
    ],
)
