# Shared helpers for the local launcher scripts.

launcher_repo_root() {
    local source_dir
    source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$source_dir/../.." && pwd
}

launcher_find_command() {
    local env_var="$1"
    local fallback_name="$2"
    shift 2

    local configured="${!env_var-}"
    if [[ -n "$configured" ]]; then
        if [[ -x "$configured" ]]; then
            printf '%s\n' "$configured"
            return 0
        fi
        if command -v "$configured" >/dev/null 2>&1; then
            command -v "$configured"
            return 0
        fi
        echo "Configured $env_var is not executable or on PATH: $configured" >&2
        return 127
    fi

    if command -v "$fallback_name" >/dev/null 2>&1; then
        command -v "$fallback_name"
        return 0
    fi

    local candidate
    for candidate in "$@"; do
        if [[ -x "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    echo "Could not find $fallback_name on PATH." >&2
    return 127
}

launcher_java() {
    launcher_find_command JAVA_BIN java \
        /opt/homebrew/opt/openjdk/bin/java \
        /usr/local/opt/openjdk/bin/java
}

launcher_maven() {
    launcher_find_command MAVEN_BIN mvn \
        /opt/homebrew/bin/mvn \
        /usr/local/bin/mvn
}

launcher_abs_path() {
    local path="$1"
    local dir
    local base
    dir="$(dirname "$path")"
    base="$(basename "$path")"

    if [[ -d "$dir" ]]; then
        (cd "$dir" && printf '%s/%s\n' "$(pwd)" "$base")
        return 0
    fi

    printf '%s\n' "$path"
}

launcher_server_config() {
    local root_dir="$1"
    local server_dir="$root_dir/2006Scape Server"
    local configured="${SERVER_CONFIG-}"

    if [[ -n "$configured" ]]; then
        if [[ "$configured" = /* ]]; then
            printf '%s\n' "$configured"
        elif [[ -f "$PWD/$configured" ]]; then
            launcher_abs_path "$PWD/$configured"
        elif [[ -f "$server_dir/$configured" ]]; then
            launcher_abs_path "$server_dir/$configured"
        elif [[ -f "$root_dir/$configured" ]]; then
            launcher_abs_path "$root_dir/$configured"
        else
            printf '%s\n' "$configured"
        fi
        return 0
    fi

    if [[ -f "$server_dir/ServerConfig.json" ]]; then
        printf '%s\n' "$server_dir/ServerConfig.json"
        return 0
    fi

    printf '%s\n' "$server_dir/ServerConfig.Sample.json"
}

launcher_require_file() {
    local path="$1"
    local message="$2"

    if [[ ! -f "$path" ]]; then
        echo "$message" >&2
        return 1
    fi
}

launcher_port_open() {
    local port="$1"

    if ! command -v nc >/dev/null 2>&1; then
        return 1
    fi

    nc -z 127.0.0.1 "$port" >/dev/null 2>&1
}
