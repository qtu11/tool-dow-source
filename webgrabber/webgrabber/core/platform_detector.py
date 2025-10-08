# Vị trí lưu: webgrabber/core/platform_detector.py
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests

class PlatformDetector:
    """Detects the platform type from a URL."""

    PLATFORMS = {
        # Git Hosting
        'github.com': {'name': 'GitHub', 'type': 'git_hosting', 'id': 'github', 'cli_tool': 'git'},
        'gitlab.com': {'name': 'GitLab', 'type': 'git_hosting', 'id': 'gitlab', 'cli_tool': 'git'},
        'bitbucket.org': {'name': 'Bitbucket', 'type': 'git_hosting', 'id': 'bitbucket', 'cli_tool': 'git'},
        'sourceforge.net': {'name': 'SourceForge', 'type': 'git_hosting', 'id': 'sourceforge', 'cli_tool': 'git'},
        'codecommit.amazonaws.com': {'name': 'AWS CodeCommit', 'type': 'git_hosting', 'id': 'aws_codecommit', 'cli_tool': 'git'},
        'dev.azure.com': {'name': 'Azure Repos', 'type': 'git_hosting', 'id': 'azure_repos', 'cli_tool': 'git'},
        'source.cloud.google.com': {'name': 'Google Cloud Source Repositories', 'type': 'git_hosting', 'id': 'gcp_source', 'cli_tool': 'gcloud'},
        'launchpad.net': {'name': 'Launchpad', 'type': 'git_hosting', 'id': 'launchpad', 'cli_tool': 'git'},
        'try.gitea.io': {'name': 'Gitea', 'type': 'git_hosting', 'id': 'gitea', 'cli_tool': 'git'},
        'gogs.io': {'name': 'Gogs', 'type': 'git_hosting', 'id': 'gogs', 'cli_tool': 'git'},
        'phabricator.services': {'name': 'Phabricator', 'type': 'git_hosting', 'id': 'phabricator', 'cli_tool': 'git'},
        'assembla.com': {'name': 'Assembla', 'type': 'git_hosting', 'id': 'assembla', 'cli_tool': 'git'},
        'savannah.gnu.org': {'name': 'Savannah', 'type': 'git_hosting', 'id': 'savannah', 'cli_tool': 'git'},
        'codeberg.org': {'name': 'Codeberg', 'type': 'git_hosting', 'id': 'codeberg', 'cli_tool': 'git'},
        'sr.ht': {'name': 'Sr.ht', 'type': 'git_hosting', 'id': 'srht', 'cli_tool': 'git'},

        # Container Registries (new type)
        'hub.docker.com': {'name': 'Docker Hub', 'type': 'container_registry', 'id': 'docker_hub', 'cli_tool': 'docker'},
        'ghcr.io': {'name': 'GitHub Container Registry', 'type': 'container_registry', 'id': 'ghcr', 'cli_tool': 'docker'},
        'registry.gitlab.com': {'name': 'GitLab Container Registry', 'type': 'container_registry', 'id': 'gitlab_registry', 'cli_tool': 'docker'},
        'ecr.aws': {'name': 'AWS ECR', 'type': 'container_registry', 'id': 'aws_ecr', 'cli_tool': 'aws'},
        'gcr.io': {'name': 'Google GCR', 'type': 'container_registry', 'id': 'gcp_gcr', 'cli_tool': 'gcloud'},
        'azurecr.io': {'name': 'Azure ACR', 'type': 'container_registry', 'id': 'azure_acr', 'cli_tool': 'az'},
        'quay.io': {'name': 'Quay.io', 'type': 'container_registry', 'id': 'quay', 'cli_tool': 'docker'},
        'goharbor.io': {'name': 'Harbor', 'type': 'container_registry', 'id': 'harbor', 'cli_tool': 'docker'},
        'cloud.docker.com': {'name': 'Docker Cloud', 'type': 'container_registry', 'id': 'docker_cloud', 'cli_tool': 'docker'},
        'jfrog.io': {'name': 'JFrog Artifactory', 'type': 'container_registry', 'id': 'jfrog', 'cli_tool': 'jfrog'},
        'sonatype.com': {'name': 'Nexus Repository', 'type': 'container_registry', 'id': 'nexus', 'cli_tool': 'docker'},

        # CI/CD (fallback to unknown or git if linked)
        'circleci.com': {'name': 'CircleCI', 'type': 'ci_cd', 'id': 'circleci'},
        'travis-ci.com': {'name': 'Travis CI', 'type': 'ci_cd', 'id': 'travis'},
        'jenkins.io': {'name': 'Jenkins', 'type': 'ci_cd', 'id': 'jenkins'},
        'drone.io': {'name': 'Drone CI', 'type': 'ci_cd', 'id': 'drone'},
        'argoproj.github.io': {'name': 'ArgoCD', 'type': 'ci_cd', 'id': 'argocd'},
        'tekton.dev': {'name': 'Tekton', 'type': 'ci_cd', 'id': 'tekton'},
        'kubernetes.io': {'name': 'Kubernetes', 'type': 'ci_cd', 'id': 'kubernetes'},
        'openshift.com': {'name': 'OpenShift', 'type': 'ci_cd', 'id': 'openshift'},

        # Domain Registrars (fallback to unknown)
        'godaddy.com': {'name': 'GoDaddy', 'type': 'domain_registrar', 'id': 'godaddy'},
        'namecheap.com': {'name': 'Namecheap', 'type': 'domain_registrar', 'id': 'namecheap'},
        'domains.google': {'name': 'Google Domains', 'type': 'domain_registrar', 'id': 'google_domains'},
        'cloudflare.com': {'name': 'Cloudflare Registrar', 'type': 'domain_registrar', 'id': 'cloudflare'},
        'bluehost.com': {'name': 'Bluehost', 'type': 'domain_registrar', 'id': 'bluehost'},
        'hostinger.com': {'name': 'Hostinger', 'type': 'domain_registrar', 'id': 'hostinger'},
        'domain.com': {'name': 'Domain.com', 'type': 'domain_registrar', 'id': 'domain_com'},
        'hover.com': {'name': 'Hover', 'type': 'domain_registrar', 'id': 'hover'},
        'dynadot.com': {'name': 'Dynadot', 'type': 'domain_registrar', 'id': 'dynadot'},
        'porkbun.com': {'name': 'Porkbun', 'type': 'domain_registrar', 'id': 'porkbun'},
        'ovh.com': {'name': 'OVH', 'type': 'domain_registrar', 'id': 'ovh'},
        'dreamhost.com': {'name': 'DreamHost', 'type': 'domain_registrar', 'id': 'dreamhost'},
        'pavietnam.vn': {'name': 'P.A Việt Nam', 'type': 'domain_registrar', 'id': 'pa_vietnam'},
        'matbao.net': {'name': 'MatBao', 'type': 'domain_registrar', 'id': 'matbao'},
        'tenten.vn': {'name': 'Tenten', 'type': 'domain_registrar', 'id': 'tenten'},
        'inet.vn': {'name': 'Inet', 'type': 'domain_registrar', 'id': 'inet'},
        'nhanhoa.com': {'name': 'Nhân Hòa', 'type': 'domain_registrar', 'id': 'nhanhoa'},

        # Cloud/PaaS
        'aws.amazon.com': {'name': 'AWS', 'type': 'paas', 'id': 'aws', 'cli_tool': 'aws'},
        'cloud.google.com': {'name': 'GCP', 'type': 'paas', 'id': 'gcp', 'cli_tool': 'gcloud'},
        'azure.microsoft.com': {'name': 'Azure', 'type': 'paas', 'id': 'azure', 'cli_tool': 'az'},
        'digitalocean.com': {'name': 'DigitalOcean', 'type': 'paas', 'id': 'digitalocean', 'cli_tool': 'doctl'},
        'linode.com': {'name': 'Linode', 'type': 'paas', 'id': 'linode', 'cli_tool': 'linode-cli'},
        'vultr.com': {'name': 'Vultr', 'type': 'paas', 'id': 'vultr', 'cli_tool': 'vultr-cli'},
        'hetzner.com': {'name': 'Hetzner', 'type': 'paas', 'id': 'hetzner', 'cli_tool': 'hcloud'},
        'cloud.oracle.com': {'name': 'Oracle Cloud', 'type': 'paas', 'id': 'oracle', 'cli_tool': 'oci'},
        'heroku.com': {'name': 'Heroku', 'type': 'paas', 'id': 'heroku', 'cli_tool': 'heroku'},
        'render.com': {'name': 'Render', 'type': 'paas', 'id': 'render', 'cli_tool': 'render-cli'},  # Giả định CLI nếu có
        'netlify.com': {'name': 'Netlify', 'type': 'paas', 'id': 'netlify', 'cli_tool': 'netlify'},
        'vercel.com': {'name': 'Vercel', 'type': 'paas', 'id': 'vercel', 'cli_tool': 'vercel'},
        'fly.io': {'name': 'Fly.io', 'type': 'paas', 'id': 'flyio', 'cli_tool': 'flyctl'},
        'railway.app': {'name': 'Railway', 'type': 'paas', 'id': 'railway', 'cli_tool': 'railway'},
        'cloudfoundry.org': {'name': 'Cloud Foundry', 'type': 'paas', 'id': 'cloudfoundry', 'cli_tool': 'cf'},
        'openshift.com': {'name': 'OpenShift', 'type': 'paas', 'id': 'openshift', 'cli_tool': 'oc'},
        'dokku.com': {'name': 'Dokku', 'type': 'paas', 'id': 'dokku', 'cli_tool': 'dokku'},
        'caprover.com': {'name': 'CapRover', 'type': 'paas', 'id': 'caprover', 'cli_tool': 'caprover'},
        'cloud66.com': {'name': 'Cloud 66', 'type': 'paas', 'id': 'cloud66', 'cli_tool': 'cx'},
        'scaleway.com': {'name': 'Scaleway', 'type': 'paas', 'id': 'scaleway', 'cli_tool': 'scw'},
        'platform.sh': {'name': 'Platform.sh', 'type': 'paas', 'id': 'platformsh', 'cli_tool': 'platform'},
        'openshift.com': {'name': 'OpenShift', 'type': 'paas', 'id': 'openshift', 'cli_tool': 'oc'},
        'dokku.com': {'name': 'Dokku', 'type': 'paas', 'id': 'dokku', 'cli_tool': 'dokku'},
        'caprover.com': {'name': 'CapRover', 'type': 'paas', 'id': 'caprover', 'cli_tool': 'caprover'},

        # ... existing ...
        'assembla.com': {'name': 'Assembla', 'type': 'git_hosting', 'id': 'assembla', 'cli_tool': 'git'},
        'beanstalkapp.com': {'name': 'Beanstalk', 'type': 'git_hosting', 'id': 'beanstalk', 'cli_tool': 'git'},
        'fogcreek.com': {'name': 'FogCreek Kiln', 'type': 'git_hosting', 'id': 'kiln', 'cli_tool': 'git'},
        'rhodecode.com': {'name': 'RhodeCode', 'type': 'git_hosting', 'id': 'rhodecode', 'cli_tool': 'git'},
        'dev.azure.com': {'name': 'Azure Repos', 'type': 'git_hosting', 'id': 'azure_repos', 'cli_tool': 'git'},
        'codecommit.amazonaws.com': {'name': 'AWS CodeCommit', 'type': 'git_hosting', 'id': 'aws_codecommit', 'cli_tool': 'aws'},
        'source.cloud.google.com': {'name': 'GCP Source Repos', 'type': 'git_hosting', 'id': 'gcp_source', 'cli_tool': 'gcloud'},
        'perforce.com': {'name': 'Helix TeamHub', 'type': 'git_hosting', 'id': 'helix', 'cli_tool': 'git'},
    }

    @staticmethod
    def detect(url: str) -> dict:
        """Detects platform from URL hostname."""
        hostname = urlparse(url).netloc.lower()
        for domain, info in PlatformDetector.PLATFORMS.items():
            if domain in hostname:
                return info
        # Fallback: Fetch page and check meta/tags if needed
        try:
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            # Example: Check for specific meta (e.g., Netlify/Vercel headers)
            if 'netlify' in response.headers.get('Server', '').lower():
                return {'name': 'Netlify', 'type': 'paas', 'id': 'netlify', 'cli_tool': 'netlify'}
            # Add more heuristics if needed
        except Exception:
            pass
        return {'name': 'Unknown', 'type': 'unknown'}
