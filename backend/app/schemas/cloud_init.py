"""
Cloud-Init Schemas - Profile fuer automatische VM-Konfiguration
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class CloudInitProfile(str, Enum):
    """Vordefinierte Cloud-Init Profile"""
    NONE = ""  # Keine Cloud-Init Konfiguration
    BASIC = "basic"  # Nur SSH-Key, Updates
    DOCKER_HOST = "docker-host"  # Docker installiert
    DOCKER_COMPOSE = "docker-compose"  # Docker + Compose Standalone
    WEB_SERVER = "web-server"  # Nginx/Apache-ready
    K8S_NODE = "k8s-node"  # Kubernetes Worker vorbereitet
    K8S_CONTROL = "k8s-control"  # Kubernetes Control Plane
    DEV_MACHINE = "dev-machine"  # Entwicklungsumgebung
    DATABASE = "database"  # Datenbank-Server
    MONITORING = "monitoring"  # Prometheus/Grafana Node
    GITLAB_RUNNER = "gitlab-runner"  # GitLab CI Runner
    MAIL_SERVER = "mail-server"  # Mail-Server Grundlagen
    NFS_CLIENT = "nfs-client"  # NFS-Client konfiguriert
    ANSIBLE_TARGET = "ansible-target"  # Optimiert fuer Ansible


# Profile-Beschreibungen fuer das Frontend
CLOUD_INIT_PROFILES = {
    "": {
        "name": "Keine",
        "description": "Keine zusaetzliche Cloud-Init Konfiguration (nur Basis-Template)",
        "packages": [],
        "groups": [],
        "services": [],
        "sysctl": {},
    },
    "basic": {
        "name": "Basic",
        "description": "SSH-Key, System-Updates, grundlegende Tools",
        "packages": ["curl", "wget", "vim", "htop", "git", "jq", "tree"],
        "groups": [],
        "services": [],
        "sysctl": {},
    },
    "docker-host": {
        "name": "Docker Host",
        "description": "Docker CE, Docker Compose Plugin, Container-Tools",
        "packages": [
            "docker-ce",
            "docker-ce-cli",
            "containerd.io",
            "docker-compose-plugin",
            "docker-buildx-plugin",
        ],
        "groups": ["docker"],
        "services": ["docker"],
        "apt_sources": {
            "docker.list": {
                "source": "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $RELEASE stable",
                "keyid": "9DC858229FC7DD38854AE2D88D81803C0EBFCD88",
                "keyring": "/etc/apt/keyrings/docker.gpg",
            }
        },
        "sysctl": {
            "net.bridge.bridge-nf-call-iptables": 1,
            "net.bridge.bridge-nf-call-ip6tables": 1,
            "net.ipv4.ip_forward": 1,
        },
    },
    "docker-compose": {
        "name": "Docker + Compose Standalone",
        "description": "Docker CE mit Standalone docker-compose Binary",
        "packages": [
            "docker-ce",
            "docker-ce-cli",
            "containerd.io",
            "docker-compose-plugin",
            "docker-buildx-plugin",
        ],
        "groups": ["docker"],
        "services": ["docker"],
        "apt_sources": {
            "docker.list": {
                "source": "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $RELEASE stable",
                "keyid": "9DC858229FC7DD38854AE2D88D81803C0EBFCD88",
                "keyring": "/etc/apt/keyrings/docker.gpg",
            }
        },
        "runcmd_extra": [
            "curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose",
            "chmod +x /usr/local/bin/docker-compose",
        ],
        "sysctl": {
            "net.bridge.bridge-nf-call-iptables": 1,
            "net.ipv4.ip_forward": 1,
        },
    },
    "web-server": {
        "name": "Web Server",
        "description": "Nginx, Certbot, grundlegende Web-Tools",
        "packages": [
            "nginx",
            "certbot",
            "python3-certbot-nginx",
            "logrotate",
        ],
        "groups": ["www-data"],
        "services": ["nginx"],
        "write_files": [
            {
                "path": "/etc/nginx/conf.d/security.conf",
                "content": """# Security Headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

# Hide Nginx version
server_tokens off;
""",
            }
        ],
        "sysctl": {
            "net.core.somaxconn": 65535,
            "net.ipv4.tcp_max_syn_backlog": 65535,
        },
    },
    "k8s-node": {
        "name": "Kubernetes Node",
        "description": "Container Runtime, kubeadm, kubectl, kubelet",
        "packages": [
            "containerd",
            "kubeadm",
            "kubectl",
            "kubelet",
            "kubernetes-cni",
            "nfs-common",
            "open-iscsi",
        ],
        "groups": [],
        "services": ["containerd", "kubelet"],
        "sysctl": {
            "net.bridge.bridge-nf-call-iptables": 1,
            "net.bridge.bridge-nf-call-ip6tables": 1,
            "net.ipv4.ip_forward": 1,
            "vm.swappiness": 0,
        },
        "runcmd_extra": [
            "swapoff -a",
            "sed -i '/ swap / s/^/#/' /etc/fstab",
            "modprobe br_netfilter",
            "modprobe overlay",
            'echo "br_netfilter" >> /etc/modules-load.d/k8s.conf',
            'echo "overlay" >> /etc/modules-load.d/k8s.conf',
        ],
    },
    "k8s-control": {
        "name": "Kubernetes Control Plane",
        "description": "K8s Control Plane mit etcd, API Server Voraussetzungen",
        "packages": [
            "containerd",
            "kubeadm",
            "kubectl",
            "kubelet",
            "kubernetes-cni",
            "etcd-client",
            "nfs-common",
        ],
        "groups": [],
        "services": ["containerd", "kubelet"],
        "sysctl": {
            "net.bridge.bridge-nf-call-iptables": 1,
            "net.bridge.bridge-nf-call-ip6tables": 1,
            "net.ipv4.ip_forward": 1,
            "vm.swappiness": 0,
            "fs.inotify.max_user_watches": 524288,
            "fs.inotify.max_user_instances": 512,
        },
        "runcmd_extra": [
            "swapoff -a",
            "sed -i '/ swap / s/^/#/' /etc/fstab",
            "modprobe br_netfilter",
            "modprobe overlay",
        ],
    },
    "dev-machine": {
        "name": "Entwicklungsumgebung",
        "description": "Build-Tools, Python, Node.js, Go",
        "packages": [
            "build-essential",
            "python3-pip",
            "python3-venv",
            "python3-dev",
            "nodejs",
            "npm",
            "golang",
            "rustc",
            "cargo",
            "default-jdk",
            "maven",
            "gradle",
            "sqlite3",
            "libpq-dev",
            "libssl-dev",
            "libffi-dev",
        ],
        "groups": [],
        "services": [],
        "runcmd_extra": [
            "pip3 install --upgrade pip setuptools wheel",
            "npm install -g yarn pnpm",
        ],
        "sysctl": {
            "fs.inotify.max_user_watches": 524288,
        },
    },
    "database": {
        "name": "Datenbank-Server",
        "description": "Optimierte Settings fuer DB-Workloads (PostgreSQL/MySQL ready)",
        "packages": [
            "postgresql-client",
            "mysql-client",
            "redis-tools",
            "libpq-dev",
        ],
        "groups": [],
        "services": [],
        "sysctl": {
            "vm.swappiness": 1,
            "vm.dirty_ratio": 40,
            "vm.dirty_background_ratio": 10,
            "net.core.somaxconn": 65535,
            "net.ipv4.tcp_max_syn_backlog": 65535,
            "fs.file-max": 2097152,
        },
        "limits": [
            "* soft nofile 65536",
            "* hard nofile 65536",
            "* soft nproc 65536",
            "* hard nproc 65536",
        ],
    },
    "monitoring": {
        "name": "Monitoring Node",
        "description": "Node Exporter, Promtail, Log-Aggregation",
        "packages": [
            "prometheus-node-exporter",
        ],
        "groups": [],
        "services": ["prometheus-node-exporter"],
        "runcmd_extra": [
            # Promtail installieren
            "curl -sL https://github.com/grafana/loki/releases/latest/download/promtail-linux-amd64.zip -o /tmp/promtail.zip",
            "unzip -o /tmp/promtail.zip -d /usr/local/bin/",
            "chmod +x /usr/local/bin/promtail-linux-amd64",
            "ln -sf /usr/local/bin/promtail-linux-amd64 /usr/local/bin/promtail",
        ],
        "sysctl": {},
    },
    "gitlab-runner": {
        "name": "GitLab CI Runner",
        "description": "GitLab Runner mit Docker Executor",
        "packages": [
            "docker-ce",
            "docker-ce-cli",
            "containerd.io",
            "gitlab-runner",
        ],
        "groups": ["docker"],
        "services": ["docker", "gitlab-runner"],
        "apt_sources": {
            "docker.list": {
                "source": "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $RELEASE stable",
                "keyid": "9DC858229FC7DD38854AE2D88D81803C0EBFCD88",
                "keyring": "/etc/apt/keyrings/docker.gpg",
            },
            "gitlab-runner.list": {
                "source": "deb https://packages.gitlab.com/runner/gitlab-runner/debian/ $RELEASE main",
                "keyid": "F6403F6544A38863DAA0B6E03F01618A51312F3F",
            },
        },
        "sysctl": {
            "net.ipv4.ip_forward": 1,
        },
    },
    "mail-server": {
        "name": "Mail-Server",
        "description": "Postfix, Dovecot Grundlagen",
        "packages": [
            "postfix",
            "dovecot-imapd",
            "dovecot-pop3d",
            "opendkim",
            "opendkim-tools",
            "spamassassin",
            "mailutils",
        ],
        "groups": [],
        "services": ["postfix"],
        "sysctl": {},
    },
    "nfs-client": {
        "name": "NFS Client",
        "description": "NFS-Mounts vorkonfiguriert",
        "packages": [
            "nfs-common",
            "autofs",
        ],
        "groups": [],
        "services": ["autofs"],
        "write_files": [
            {
                "path": "/etc/auto.master.d/nfs.autofs",
                "content": "/mnt/nfs /etc/auto.nfs --timeout=300\n",
            },
            {
                "path": "/etc/auto.nfs",
                "content": "# Format: mountpoint -options server:/path\n# Beispiel: data -fstype=nfs4,rw nas.local:/volume1/data\n",
            },
        ],
        "sysctl": {},
    },
    "ansible-target": {
        "name": "Ansible Target",
        "description": "Optimiert fuer Ansible-Verwaltung",
        "packages": [
            "python3",
            "python3-apt",
            "python3-pip",
            "sudo",
            "acl",
        ],
        "groups": [],
        "services": [],
        # Sudoers wird automatisch durch den Admin-User konfiguriert
        # (siehe generate_user_data: "sudo": "ALL=(ALL) NOPASSWD:ALL")
        "sysctl": {},
    },
}


class CloudInitProfileInfo(BaseModel):
    """Schema fuer Cloud-Init Profil-Information"""
    id: str
    name: str
    description: str
    packages: List[str] = []
    groups: List[str] = []
    services: List[str] = []


class CloudInitConfig(BaseModel):
    """Schema fuer Cloud-Init Konfiguration"""
    profile: CloudInitProfile = Field(default=CloudInitProfile.NONE)
    ssh_authorized_keys: List[str] = Field(default_factory=list)
    packages: List[str] = Field(default_factory=list)
    runcmd: List[str] = Field(default_factory=list)


class CloudInitCallbackRequest(BaseModel):
    """Schema fuer Cloud-Init Phone-Home Callback"""
    hostname: str
    instance_id: Optional[str] = None
    ip_address: Optional[str] = None
    fqdn: Optional[str] = None
    status: str = "completed"
    timestamp: Optional[str] = None
    pub_key_ecdsa: Optional[str] = None
    pub_key_ed25519: Optional[str] = None


class CloudInitCallbackResponse(BaseModel):
    """Antwort auf Cloud-Init Callback"""
    success: bool
    message: str
    vm_name: Optional[str] = None
