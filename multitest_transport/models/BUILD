# MTT data models.

load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_library", "py_test", "pytype_strict_library", "third_party")

package(
    default_applicable_licenses = ["//multitest_transport:license"],
    default_visibility = ["//multitest_transport"],
)

licenses(["notice"])

pytype_strict_library(
    name = "build_lib",
    srcs = [
        "build.py",
    ],
    deps = [
        ":ndb_models_lib",
        "//multitest_transport/plugins:plugin_base",
        "//multitest_transport/util",
    ],
)

py_test(
    name = "build_test",
    srcs = [
        "build_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":build_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
    ],
)

pytype_strict_library(
    name = "config_encoder_lib",
    srcs = [
        "config_encoder.py",
    ],
    deps = [
        ":messages_lib",
        ":ndb_models_lib",
        third_party("protorpc"),
        third_party("yaml"),
    ],
)

py_test(
    name = "config_encoder_test",
    srcs = [
        "config_encoder_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":config_encoder_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
    ],
)

pytype_strict_library(
    name = "config_set_helper_lib",
    srcs = [
        "config_set_helper.py",
    ],
    deps = [
        ":build_lib",
        ":config_encoder_lib",
        ":messages_lib",
        ":ndb_models_lib",
        "//multitest_transport/test_scheduler:download_util_lib",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
    ],
)

py_test(
    name = "config_set_helper_test",
    srcs = [
        "config_set_helper_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":build_lib",
        ":config_encoder_lib",
        ":config_set_helper_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/test_scheduler",
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
    ],
)

pytype_strict_library(
    name = "event_log_lib",
    srcs = ["event_log.py"],
    deps = [
        ":ndb_models_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
    ],
)

py_test(
    name = "event_log_test",
    srcs = [
        "event_log_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":event_log_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
    ],
)

pytype_strict_library(
    name = "messages_lib",
    srcs = [
        "messages.py",
    ],
    deps = [
        ":build_lib",
        ":event_log_lib",
        ":ndb_models_lib",
        ":sql_models_lib",
        "//multitest_transport/plugins:plugin_base",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("google/oauth2:credentials"),
        third_party("google/oauth2:service_account"),
        third_party("protorpc"),
        third_party("pytz"),
    ],
)

py_test(
    name = "messages_test",
    srcs = [
        "messages_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":messages_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
    ],
)

py_library(
    name = "models",
    deps = [
        ":build_lib",
        ":config_encoder_lib",
        ":config_set_helper_lib",
        ":event_log_lib",
        ":messages_lib",
        ":ndb_models_lib",
        ":sql_models_lib",
        ":test_run_hook_lib",
    ],
)

pytype_strict_library(
    name = "ndb_models_lib",
    srcs = [
        "ndb_models.py",
    ],
    deps = [
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster:common_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("protorpc"),
    ],
)

# Use py_library as sqlalchemy imports don't work with pytype_strict_library
py_library(
    name = "sql_models_lib",
    srcs = ["sql_models.py"],
    deps = [
        "//multitest_transport/util",
        third_party("sqlalchemy"),
    ],
)

py_test(
    name = "sql_models_test",
    srcs = [
        "sql_models_test.py",
    ],
    deps = [
        ":sql_models_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/util",
        third_party("absl/testing:absltest"),
        third_party("absl/testing:parameterized"),
        third_party("sqlalchemy"),
        third_party("sqlite3"),
    ],
)

pytype_strict_library(
    name = "test_run_hook_lib",
    srcs = ["test_run_hook.py"],
    deps = [
        ":event_log_lib",
        ":ndb_models_lib",
        "//multitest_transport/plugins:plugin_base",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        "@tradefed_cluster//tradefed_cluster/plugins:base_lib",
    ],
)

py_test(
    name = "test_run_hook_test",
    srcs = [
        "test_run_hook_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":test_run_hook_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster:command_task_api_lib",
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
    ],
)
