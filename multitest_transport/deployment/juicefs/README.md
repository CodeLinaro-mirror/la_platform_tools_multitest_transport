# JuiceFS Deployment for Lab Environments

This project provides a comprehensive solution for deploying a [JuiceFS](https://juicefs.com/) distributed file system within a lab environment. It is designed with a clear separation between a central **Service Host** (which provides the JuiceFS volume) and multiple **Client Hosts** (which consume the volume).

This setup allows any machine in the lab to mount the shared filesystem and use
it as a local Docker volume, making it ideal for applications that require
shared, persistent storage, such
as the mtt container.

## Architecture Overview

The system is composed of two main parts:

1.  **JuiceFS Service Host**: A dedicated Linux server that runs the entire JuiceFS backend stack using Docker Compose. This includes:
    *   **MySQL**: The metadata engine for JuiceFS.
    *   **SeaweedFS**: The S3-compatible object storage for the actual file data.
    *   **JuiceFS Mount Container**: A container that formats and mounts the JuiceFS volume, making it available to the host.

2.  **JuiceFS Client Host**: Any Linux machine in the lab that wants to access the shared file system. It uses a simple shell script to:
    *   Install the JuiceFS client if needed.
    *   Mount the remote JuiceFS volume to a local directory on the host.
    *   Create a Docker named volume that is "bound" to this local directory, making the shared file system available to any container on the client machine.

---

## 1. Setting Up the JuiceFS Service Host

This is a one-time setup on a dedicated storage server in your lab.

### Prerequisites

*   A Linux server with Docker and Docker Compose installed. For installation of docker compose, refer to the [official Docker Compose installation guide](https://docs.docker.com/compose/install/linux/#install-using-the-repository).
*   `sudo` access

### Firewall Requirements

For client machines to connect to the JuiceFS service, the following TCP ports
must be open on the **Service Host**:

*   **MYSQL_PORT**: For JuiceFS metadata engine communication. Default to be 3306. Pick a new one if port conflict on the service host.
*   **SEAWEEDFS_S3_PORT**: For JuiceFS data storage access. Default to be 8333. Pick a new one if port conflict on the service host.

### Files

*   `jfs_service.sh`: The main script for managing the service stack.
*   `docker-compose.jfs.yml`: The Docker Compose file defining the backend services.
*   `entrypoint.sh`: A helper script for graceful umount.
*   `.env`: A configuration file

### Setup Steps

1.  **Place Files**: Copy `jfs_service.sh`, `docker-compose.jfs.yml`, `entrypoint.sh` and `.env` into a single directory on your chosen server.

2.  **Update `.env` Configuration File**: The configuration is using environment
variables in .env. The following 3 env variables are the most important.
    *   `JFS_VOLUME_IP`: The network-accessible IP address of the JuiceFS Service Host. This is crucial for clients to connect.
    *   `JFS_CAPACITY`: Defines the total storage capacity (in GiB) of the JuiceFS filesystem. It should be less than the capacity of the root partition of the service host.
    *   `CACHE_SIZE`: Specifies the maximum size (in GiB) for the persistent cache managed by the Cache Manager application. It should be less than 80% of the JFS_CAPACITY.

You should make sure all env variables in the .env are set. Or you can provide
the values with corresponding flags of `jfs_service.sh`. You can see all flags
of `jfs_service.sh` with `./jfs_service.sh --help` command.

3.  **Make Script Executable**:

    ```bash
    sudo chmod a+x jfs_service.sh
    ```

4.  **Start the Service**:
    If you have updated the .env file.

    ```bash
    sudo ./jfs_service.sh up
    ```

    or use flags

    ```bash
    sudo ./jfs_service.sh up [flags]
    ```

    This command will:
    *   Start the MySQL and SeaweedFS containers.
    *   Format the JuiceFS volume.
    *   Create the host mount directory (`HOST_MNT_PATH`).
    *   Mount the JuiceFS volume to that directory.
    *   Create a Docker named volume `mtt-jfs` that points to this host directory, making it shareable.

### Managing the Service

*   **Stop the service and delete all data**:

    ```bash
    sudo ./jfs_service.sh down
    ```

    or with the same flags

    ```bash
    sudo ./jfs_service.sh down [flags]
    ```
    **Warning**: This is a destructive operation. You should tear down all
    clients before you tear down the service. It will ask for confirmation
    before wiping the filesystem data.

---

## 2. Setting Up a JuiceFS Client Host

Perform these steps on any machine that needs to access the shared JuiceFS
volume.

### Prerequisites

*   A Linux machine with network access to the JuiceFS Service Host via IP.
*   `sudo` access.
*   Docker installed (if you intend to use the volume with containers).

### Files

*   `jfs_client.sh`: The script for managing the client-side mount.
*   `.env`: A configuration file.

### Setup Steps

1.  **Place Script**: Copy `jfs_client.sh` to a directory on the client machine.

2.  **Update `.env` Configuration File**: This should be the same .env file as that used on the service host.

3.  **Make Script Executable**:

    ```bash
    sudo chmod +x jfs_client.sh
    ```

4.  **Mount the Volume**:

    ```bash
    sudo ./jfs_client.sh up
    ```

    or with flags

    ```bash
    sudo ./jfs_client.sh up [flags]
    ```
    This command will:
    *   Check if the `juicefs` client is installed and install it if it's missing.
    *   Check if the remote JuiceFS service is ready.
    *   Mount the remote volume to the local `HOST_MNT_PATH`.
    *   Create a local Docker named volume called `mtt-jfs` that is bound to this mount point.

### Using the Shared Volume with Docker

Once `./jfs_client.sh up` has been run, any container on the client machine can
use the shared filesystem by mounting the `mtt-jfs` volume.

**Example `docker run` command:**

```bash
docker run -it --rm -v mtt-jfs:/shared_data alpine ls -l /shared_data
```

**Example for MTT `cli.py`:**
To use this with your mtt, you would use the `--bind_jfs_volume` flag:

```bash
mtt start --bind_jfs_volume=mtt-jfs [other_args...]
```

### Unmounting the Volume

*   **Unmount the filesystem and remove the Docker volume**:

    ```bash
    sudo ./jfs_client.sh down
    ```

    or with the same flags

    ```bash
    sudo ./jfs_client.sh down [flags]
    ```
    This will safely remove the Docker volume and then unmount the JuiceFS
    filesystem from the host.
