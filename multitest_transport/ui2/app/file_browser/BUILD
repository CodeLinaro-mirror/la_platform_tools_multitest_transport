load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

per_file_sass_binaries(
    name = "styles",
    srcs = glob(["*.scss"]),
    allow_imports = True,
    deps = ["//multitest_transport/ui2:constants"],
)

ng_module(
    name = "file_browser",
    srcs = [
        "file_browser.ts",
        "file_browser_module.ts",
        "file_browser_page.ts",
    ],
    assets = [
        ":styles",
        "file_browser_page.ng.html",
        "file_browser.ng.html",
    ],
    strict_templates = False,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular2:core"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:router"),
        third_party_js("angular_components:cdk_a11y"),
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
        "file_browser_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":file_browser",
        third_party_js("angular2:common"),
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular_components:material_legacy_dialog"),
        third_party_js("angular_components:material_snack_bar"),
        third_party_js("moment:typings"),
        third_party_js("rxjs"),
        third_party_js("typings/jasmine"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/testing:angular_util",
        "//multitest_transport/ui2/app/testing:jasmine_util",
        "//multitest_transport/ui2/app/testing:test_util",
    ],
)
