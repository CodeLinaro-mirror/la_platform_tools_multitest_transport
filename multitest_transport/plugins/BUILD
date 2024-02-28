# MTT default plugins.
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_test", "pytype_strict_library", "third_party")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

pytype_strict_library(
    name = "android_lib",
    srcs = [
        "android.py",
    ],
    deps = [
        ":plugin_base",
        "//multitest_transport/util:constant_lib",
        "//multitest_transport/util:env_lib",
        "//multitest_transport/util:errors_lib",
        "//multitest_transport/util:file_util_lib",
        "//multitest_transport/util:oauth2_util_lib",
        third_party("apiclient"),
        third_party("httplib2"),
    ],
)

py_test(
    name = "android_test",
    srcs = [
        "android_test.py",
    ],
    deps = [
        ":android_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
    ],
)


pytype_strict_library(
    name = "apfe_lib",
    srcs = [
        "apfe.py",
    ],
    deps = [
        ":plugin_base",
        "//multitest_transport/models:event_log_lib",
        "//multitest_transport/models:messages_lib",
        "//multitest_transport/models:ndb_models_lib",
        "//multitest_transport/util",
        "//multitest_transport/util:apfe_client_lib",
        "//third_party/py/protorpc:protorpc_all",
    ],
)

py_test(
    name = "apfe_test",
    srcs = [
        "apfe_test.py",
    ],
    deps = [
        ":apfe_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/models:ndb_models_lib",
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "http_lib",
    srcs = [
        "http.py",
    ],
    deps = [
        ":plugin_base",
        "//multitest_transport/util",
    ],
)

py_test(
    name = "http_test",
    srcs = [
        "http_test.py",
    ],
    deps = [
        ":http_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/util",
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "file_upload_hook_lib",
    srcs = [
        "file_upload_hook.py",
    ],
    deps = [
        ":plugin_base",
        "//multitest_transport/util",
    ],
)

py_test(
    name = "file_upload_hook_test",
    srcs = [
        "file_upload_hook_test.py",
    ],
    deps = [
        ":file_upload_hook_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/models",
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "gcs_lib",
    srcs = [
        "gcs.py",
    ],
    deps = [
        ":file_upload_hook_lib",
        ":plugin_base",
        "//multitest_transport/models",
        "//multitest_transport/util",
        third_party("apiclient"),
    ],
)

py_test(
    name = "gcs_test",
    srcs = [
        "gcs_test.py",
    ],
    deps = [
        ":gcs_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("apiclient"),
    ],
)

pytype_strict_library(
    name = "google_drive_lib",
    srcs = [
        "google_drive.py",
    ],
    deps = [
        ":plugin_base",
        "//multitest_transport/util:constant_lib",
        "//multitest_transport/util:env_lib",
        "//multitest_transport/util:errors_lib",
        "//multitest_transport/util:file_util_lib",
        "//multitest_transport/util:oauth2_util_lib",
        third_party("apiclient"),
    ],
)

py_test(
    name = "google_drive_test",
    srcs = [
        "google_drive_test.py",
    ],
    deps = [
        ":google_drive_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("apiclient"),
    ],
)

pytype_strict_library(
    name = "plugins",
    srcs = [
        "__init__.py",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":android_lib",
        ":apfe_lib",
        ":plugin_base",
        ":gcs_lib",
        ":google_drive_lib",
        ":http_lib",
        ":web_hook_lib",
        third_party("apiclient"),
    ],
)

pytype_strict_library(
    name = "plugin_base",
    srcs = [
        "base.py",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":registry_lib",
        "//multitest_transport/models:ndb_models_lib",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        third_party("google/auth:credentials"),
    ],
)

pytype_strict_library(
    name = "registry_lib",
    srcs = [
        "registry.py",
    ],
)

py_test(
    name = "registry_test",
    srcs = [
        "registry_test.py",
    ],
    deps = [
        ":registry_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "web_hook_lib",
    srcs = [
        "web_hook.py",
    ],
    deps = [
        ":plugin_base",
        "@tradefed_cluster//tradefed_cluster/services:app_manager_lib",
    ],
)

py_test(
    name = "web_hook_test",
    srcs = [
        "web_hook_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":web_hook_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/models",
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
        third_party("absl/testing:absltest"),
    ],
)
