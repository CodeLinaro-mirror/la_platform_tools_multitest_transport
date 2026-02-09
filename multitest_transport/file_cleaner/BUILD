# MTT file cleaner to clean up unused files inside docker.
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_test", "pytype_strict_library", "third_party")

package(
    default_applicable_licenses = ["//multitest_transport:license"],
    default_visibility = ["//multitest_transport"],
)

licenses(["notice"])

pytype_strict_library(
    name = "criterion_lib",
    srcs = ["criterion.py"],
    deps = [
        "//multitest_transport/models:messages_lib",
        "//multitest_transport/models:ndb_models_lib",
        third_party("pytimeparse"),
    ],
)

py_test(
    name = "criterion_test",
    srcs = ["criterion_test.py"],
    strict_deps = False,
    deps = [
        ":criterion_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("pyfakefs:fake_filesystem_unittest"),
    ],
)

pytype_strict_library(
    name = "file_cleaner_lib",
    srcs = ["file_cleaner.py"],
    deps = [
        ":policy_lib",
        "//multitest_transport/models:messages_lib",
        third_party("absl:app"),
        third_party("absl/flags"),
        third_party("protorpc"),
        third_party("requests"),
    ],
)

py_test(
    name = "file_cleaner_test",
    srcs = ["file_cleaner_test.py"],
    strict_deps = False,
    deps = [
        ":file_cleaner_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/util:env_lib",
        third_party("absl/testing:absltest"),
        third_party("requests_mock"),
        third_party("pyfakefs:fake_filesystem_unittest"),
    ],
)

pytype_strict_library(
    name = "operation_lib",
    srcs = ["operation.py"],
    deps = [
        "//multitest_transport/models:messages_lib",
        "//multitest_transport/models:ndb_models_lib",
        "//multitest_transport/util:file_util_lib",
    ],
)

py_test(
    name = "operation_test",
    srcs = ["operation_test.py"],
    strict_deps = False,
    deps = [
        ":operation_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/util:env_lib",
        third_party("absl/testing:absltest"),
        third_party("pyfakefs:fake_filesystem_unittest"),
    ],
)

pytype_strict_library(
    name = "policy_lib",
    srcs = ["policy.py"],
    deps = [
        ":criterion_lib",
        ":operation_lib",
        "//multitest_transport/models:messages_lib",
        "//multitest_transport/models:ndb_models_lib",
    ],
)

py_test(
    name = "policy_test",
    srcs = ["policy_test.py"],
    strict_deps = False,
    deps = [
        ":policy_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/util:env_lib",
        third_party("absl/testing:absltest"),
        third_party("pyfakefs:fake_filesystem_unittest"),
    ],
)
