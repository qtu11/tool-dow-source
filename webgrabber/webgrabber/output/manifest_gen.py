# webgrabber/webgrabber/output/manifest_gen.py

import datetime


def generate_manifest(base_url, resources):
    """Generate manifest from Resource objects"""

    # Handle both list and dict
    if isinstance(resources, dict):
        resources = list(resources.values())

    manifest = {
        'url': base_url,
        'capture_date': datetime.datetime.now().isoformat(),
        'total_resources': len(resources),
        'resources': []
    }

    type_counts = {}
    source_counts = {}

    for resource in resources:
        try:
            res_data = {
                'url': resource.url,
                'type': resource.type,
                'status': resource.status,
                'source': resource.source,
                'size': len(resource.data) if resource.data else 0
            }

            manifest['resources'].append(res_data)
            type_counts[resource.type] = type_counts.get(resource.type, 0) + 1
            source_counts[resource.source] = source_counts.get(source_counts, 0) + 1
        except AttributeError:
            continue

    manifest['by_type'] = type_counts
    manifest['by_source'] = source_counts

    return manifest