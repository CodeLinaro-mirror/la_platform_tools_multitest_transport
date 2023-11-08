# MTT core services.
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_library", "py_test", "pytype_strict_library", "third_party")

package(
    default_applicable_licenses = ["//multitest_transport:license"],
    default_visibility = ["//multitest_transport"],
)

licenses(["notice"])

pytype_strict_library(
    name = "config_loader_lib",
    srcs = [
        "config_loader.py",
    ],
    deps = [
        "//multitest_transport/models",
        third_party("yaml"),
    ],
)

py_library(
    name = "cron_lib",
    srcs = glob(["cron/*.py"]),
    deps = [
        third_party("antlr3:v3_1_1"),
    ],
)

pytype_strict_library(
    name = "cron_kicker_lib",
    srcs = [
        "cron_kicker.py",
    ],
    deps = [
        ":cron_lib",
        "//multitest_transport/test_scheduler",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster:common_lib",
        "@tradefed_cluster//tradefed_cluster/services:app_manager_lib",
        "@tradefed_cluster//tradefed_cluster/services:task_scheduler_lib",
        third_party("antlr3:v3_1_1"),
        third_party("flask"),
        third_party("pytz"),
        third_party("yaml"),
    ],
)

py_test(
    name = "cron_kicker_test",
    srcs = [
        "cron_kicker_test.py",
    ],
    data = [
        "//multitest_transport/gae_configs",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":cron_kicker_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
        third_party("absl/testing:absltest"),
        third_party("webtest"),
    ],
)

pytype_strict_library(
    name = "ndb_upgrader_lib",
    srcs = [
        "ndb_upgrader.py",
    ],
    deps = [
        "//multitest_transport/models",
    ],
)

py_test(
    name = "ndb_upgrader_test",
    srcs = [
        "ndb_upgrader_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":ndb_upgrader_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster/util:ndb_test_lib",
        third_party("absl/testing:absltest"),
        third_party("protorpc"),
    ],
)

pytype_strict_library(
    name = "app_lib",
    srcs = [
        "app.py",
    ],
    deps = [
        ":config_loader_lib",
        ":cron_kicker_lib",
        ":ndb_upgrader_lib",
        ":service_checker_lib",
        "//multitest_transport/models",
        "//multitest_transport/test_scheduler",
        "//multitest_transport/test_scheduler:download_util_lib",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster:common_lib",
        third_party("flask"),
    ],
)

pytype_strict_library(
    name = "service_checker_lib",
    srcs = [
        "service_checker.py",
    ],
    deps = [
        "//multitest_transport/models:sql_models_lib",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("requests"),
    ],
)

py_test(
    name = "service_checker_test",
    srcs = [
        "service_checker_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":service_checker_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster/util:ndb_test_lib",
    ],
)
