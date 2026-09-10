# Multitest Transport `init.sh` Workflow Analysis

> [!TIP] **Maintaining this Documentation with Gemini Coder** This workflow
> document and its diagram are generated and maintained by Gemini Coder.
> Whenever `init.sh` undergoes changes or refactoring, you can easily update
> this document by opening both `init.sh` and `init_script_workflow.md` in Cider
> and prompting Gemini Coder: *"I have refactored init.sh. Please review the
> changes and update init_script_workflow.md and its workflow diagram to
> match."*

The `init.sh` script serves as the primary initialization and entry point for
the Multitest Transport (MTT) container. It handles environment setup, proxy
configuration, dependency management, and the conditional startup of controller
and worker services depending on the container's operational mode.

---

<!-- LINT.IfChange -->

## 1. Operational Modes Overview

The script dictates which feature sets (`ENABLE_CONTROLLER_FEATURES` and
`ENABLE_WORKER_FEATURES`) activate based on two main variables:
`MTT_CONTROL_SERVER_URL` and `OPERATION_MODE`.

| Mode | `MTT_CONTROL_SERVER_URL` | `OPERATION_MODE` | Controller Features | Worker Features | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Standalone** | Unset | Unset / Default | **Enabled** | **Enabled** | Runs both Controller (RabbitMQ, OLC, DB) and Worker (ADB, CVD, Lab Server/TF) locally. |
| **Controller** | Unset | `on_premise` | **Enabled** | Disabled | Operates exclusively as the central control plane. |
| **Worker** | Set (Remote URL) | `on_premise` / Any | Disabled | **Enabled** | Operates as a remote worker node connecting back to the specified Controller. |

---

## 2. Core Workflow Stages

### Stage 1: Initialization & Proxy Setup

-   **Environment Loading:** Merges environment variables from the MTT CLI and
    Dockerfile defaults.
-   **Certificate Management:** Imports any custom CA certificates located in
    `/usr/local/share/ca-certificates/` into the Java trust store via `keytool`,
    ensuring secure TLS connectivity for Java daemons.
-   **Proxy Configuration:** Converts `HTTP_PROXY`, `HTTPS_PROXY`, and
    `NO_PROXY` into Java system properties (`JAVA_TOOL_OPTIONS`).
-   **Temporary Mounts:** Symlinks temporarily mounted files from `/tmp/.mnt`
    into the persistent ` local_file_store`.
-   **Pre-Run Hooks:** Executes `/mtt/scripts/init_pre_run.sh` and
    `/mtt/scripts/mysql.sh` if present.

### Stage 2: Controller Features (If Enabled)

-   **RabbitMQ:** Sets up PID directories and launches `rabbitmq-server`,
    waiting for it to initialize.
-   **OmniLab Subsystem (If `IS_OMNILAB_BASED`):**
    -   Initializes and starts the MySQL database daemon.
    -   Optionally launches the Device Config Server
        (`device_config_server_deploy.jar`).
    -   Launches the OmniLab Client (OLC) Server (`ats_olc_server_deploy.jar`)
        and records its process ID as `CONTROLLER_MAIN_PID`.

### Stage 3: ATS Serve Script (Always Executed)

-   Regardless of mode, `/mtt/serve.sh` is launched in the background, piping
    its logs through `multilog` into `MTT_CONTROL_SERVER_LOG_DIR`.

### Stage 4: Worker Features (If Enabled)

-   **TradeFed Setup:** Prepares `host-config.xml` and populates the
    preconfigured virtual device pool from `REMOTE_VIRTUAL_DEVICES`.
-   **ADB Daemon:** Starts `adb start-server` and configures `socat` proxies to
    forward port `5037` traffic appropriately (local container vs. host ADB).
-   **Cuttlefish / Local Virtual Devices:** If `MAX_LOCAL_VIRTUAL_DEVICES > 0`,
    configures `rsyslogd`, generates IPv6 bridge subnets, starts
    `cuttlefish-common`, and launches `ndppd`.
-   **Test Execution Engine:**
    -   *TradeFed Mode (Non-OmniLab):* Launches `tradefed.sh` in the background
        and records its process ID as `WORKER_MAIN_PID`.
    -   *OmniLab Mode:* Sets up persistent caching
        (`cache_manager_server_deploy.jar`) if enabled, configures JIT emulator
        flags, and launches the Mobile Harness OSS Lab Server
        (`lab_server_oss_deploy.jar`) in the background, recording its process
        ID as `WORKER_MAIN_PID`. If `MTT_CONNECT_LABSERVER_TO_CONFIG_SERVER` is
        set to `true`, it configures the Lab Server to connect to the external
        Config Service via gRPC; otherwise, it falls back to using the local
        `/deviceinfra/lab_server_api_config.textproto`.

### Stage 5: Post-Run Hook & Service Lifecycle Management

-   **Post-Run Hook:** Executes `/mtt/scripts/init_post_run.sh` if present after
    all services (controller, common, and worker test runner) have started,
    allowing post-startup configuration (such as starting the Wrangler agent).
-   **Service Lifecycle Management (`wait_for_services`):** Waits for the
    controller process, worker process, or both (in Standalone mode) to finish,
    and propagates the exit code.

---

## 3. Workflow Diagram

```mermaid
<!--#include file="init_script_workflow.mermaid"-->
```

<!-- LINT.ThenChange(init.sh) -->