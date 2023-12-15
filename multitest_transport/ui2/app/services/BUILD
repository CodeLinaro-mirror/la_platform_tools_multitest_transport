load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

# MTT service package
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
    name = "services",
    srcs = [
        "analytics_service.ts",
        "app_data.ts",
        "auth_dialog.ts",
        "auth_service.ts",
        "error_dialog.ts",
        "feedback_service.ts",
        "file_service.ts",
        "index.ts",
        "mtt_client.ts",
        "mtt_lab_models.ts",
        "mtt_models.ts",
        "mtt_object_map.ts",
        "notifier.ts",
        "notifier_dialog.ts",
        "services_module.ts",
        "storage_service.ts",
        "strict_params.ts",
        "tfc_client.ts",
        "tfc_models.ts",
        "user_service.ts",
    ],
    assets = [
        ":styles",
        "auth_dialog.ng.html",
        "error_dialog.ng.html",
        "notifier_dialog.ng.html",
    ],
    strict_templates = False,
    deps = [
        third_party_js("angular2:common_http"),
        third_party_js("angular2:core"),
        third_party_js("angular2:forms"),
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:material_button"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("angular_components:material_form_field"),
        third_party_js("angular_components:material_icon"),
        third_party_js("angular_components:material_input"),
        third_party_js("angular_components:material_snack_bar"),
        third_party_js("rxjs"),
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "analytics_service_test.ts",
        "file_service_test.ts",
        "mtt_client_test.ts",
        "mtt_lab_models_test.ts",
        "mtt_models_test.ts",
        "mtt_object_map_test.ts",
        "storage_service_test.ts",
        "strict_params_test.ts",
        "tfc_client_test.ts",
        "user_service_test.ts",
    ],
    deps = [
        ":services",
        third_party_js("angular2:common_http"),
        third_party_js("angular2:common_http_testing"),
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("rxjs"),
        third_party_js("typings/jasmine"),
        "//multitest_transport/ui2/app/testing:test_util",
    ],
)
