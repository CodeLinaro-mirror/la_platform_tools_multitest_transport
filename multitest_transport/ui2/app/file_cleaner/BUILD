load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

per_file_sass_binaries(
    name = "styles",
    srcs = glob(["*.scss"]),
    visibility = ["//visibility:private"],
    deps = ["//multitest_transport/ui2:constants"],
)

ng_module(
    name = "file_cleaner",
    srcs = [
        "file_cleaner_config_edit_page.ts",
        "file_cleaner_criterion_form.ts",
        "file_cleaner_module.ts",
        "file_cleaner_operation_form.ts",
        "file_cleaner_policy_edit_page.ts",
        "file_cleaner_setting_list.ts",
    ],
    assets = [
        ":styles",
        "file_cleaner_config_edit_page.ng.html",
        "file_cleaner_criterion_form.ng.html",
        "file_cleaner_operation_form.ng.html",
        "file_cleaner_policy_edit_page.ng.html",
        "file_cleaner_setting_list.ng.html",
    ],
    strict_templates = False,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular2:core"),
        third_party_js("angular2:router"),
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:material_button"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "file_cleaner_config_edit_page_test.ts",
        "file_cleaner_criterion_form_test.ts",
        "file_cleaner_operation_form_test.ts",
        "file_cleaner_policy_edit_page_test.ts",
        "file_cleaner_setting_list_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":file_cleaner",
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular2:router_testing"),
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("rxjs"),
        third_party_js("typings/jasmine"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/testing:jasmine_util",
        "//multitest_transport/ui2/app/testing:test_util",
    ],
)
