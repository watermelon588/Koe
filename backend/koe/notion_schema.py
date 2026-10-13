"""Additive, approved Notion properties. Never converts, renames or deletes a property.
https://developers.notion.com/reference/update-a-data-source
"""
import hashlib
import json

from koe import notion_service as service

TYPES = ('rich_text', 'number', 'checkbox', 'date', 'url', 'email', 'select', 'multi_select')


def prepare_write(properties):
    if not isinstance(properties, list) or not 1 <= len(properties) <= 10:
        raise ValueError('Provide 1–10 new property definitions.')
    normalized, names = [], set()
    for prop in properties:
        if not isinstance(prop, dict) or set(prop) - {'name', 'type', 'options'}:
            raise ValueError('Each new property accepts only name, type and optional select options.')
        name, kind = prop.get('name'), prop.get('type')
        if not isinstance(name, str) or not 1 <= len(name) <= 100 or name != name.strip() or any(ord(c) < 32 for c in name):
            raise ValueError('Use an explicit property name of 1–100 characters without surrounding whitespace.')
        if name.casefold() in names or name.casefold() in {n.casefold() for n in ('Date', *service.WORKFLOW)}:
            raise ValueError('Property names must be unique and cannot replace workflow/tracking fields.')
        if kind not in TYPES: raise ValueError('Choose a supported explicit type; computed, status, title, people and relation creation are excluded.')
        definition = {'name': name, 'type': kind}
        if kind in ('select', 'multi_select'):
            options = prop.get('options')
            if not isinstance(options, list) or not 1 <= len(options) <= 30 or any(
                not isinstance(o, str) or not 1 <= len(o) <= 100 or o != o.strip() or ',' in o
                or any(ord(c) < 32 for c in o) for o in options) or len({o.casefold() for o in options}) != len(options):
                raise ValueError('Select/multi-select needs 1–30 explicit unique option names; never invent options.')
            definition['options'] = list(options)
        elif 'options' in prop:
            raise ValueError('Options are allowed only for select/multi-select properties.')
        normalized.append(definition)
        names.add(name.casefold())
    return {'properties': normalized, 'destination': service.configured_destination()}


def contract(schema):
    result = {}
    for name, prop in schema.get('properties', {}).items():
        if not isinstance(prop, dict) or not isinstance(prop.get('id'), str) or not isinstance(prop.get('type'), str):
            raise service.NotionError('Notion returned incomplete property identities.', 'notion_incomplete')
        kind = prop['type']
        result[name] = {'id': prop['id'], 'type': kind, 'configuration': prop.get(kind, {})}
    return result


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def additions(properties, existing):
    names, result = {name.casefold() for name in existing}, {}
    for prop in properties:
        if prop['name'].casefold() in names:
            raise service.NotionError('A requested property already exists. No existing property will be changed.', 'notion_schema_exists')
        kind = prop['type']
        configuration = ({'options': [{'name': option} for option in prop['options']]} if kind in ('select', 'multi_select')
                         else {'format': 'number'} if kind == 'number' else {})
        result[prop['name']] = {kind: configuration}
    if len(json.dumps({**existing, **result}, ensure_ascii=False).encode()) > 50_000:
        raise service.NotionError('The projected schema exceeds the 50 KB size bound.', 'notion_schema_size')
    return result


async def prepare_proposal(args):
    async with service.client() as api:
        source_id, schema, _ = await service.source(api)
    previous = contract(schema)
    additions(args['properties'], previous)
    name = service.plain(schema.get('title', [])) or 'configured Notion workspace'
    frozen = {**args, 'expected_source': source_id, 'expected_schema': previous, 'schema_version': fingerprint(previous)}
    summary = (f"Add Notion properties in {name}: {json.dumps(args['properties'], ensure_ascii=False)}. "
               f"Destination: {args['destination']}. Existing properties and records are retained; no record values are filled.")
    return frozen, summary


async def add_properties(*, properties, destination, expected_source, expected_schema, schema_version, request_id):
    checked = prepare_write(properties)
    if checked['destination'] != destination:
        raise service.NotionError('The Notion destination changed. Propose again.', 'notion_destination')
    async with service.lock(), service.client() as api:
        source_id, schema, _ = await service.source(api)
        previous = contract(schema)
        if source_id != expected_source or previous != expected_schema or fingerprint(previous) != schema_version:
            raise service.NotionError('The Notion schema/source changed after the preview. Propose again.', 'notion_stale')
        payload = additions(checked['properties'], previous)
        result = await service.call(api, 'PATCH', '/data_sources/' + source_id, json={'properties': payload})
        if 'properties' not in result:
            returned_source, result, _ = await service.source(api)
            if returned_source != source_id:
                raise service.NotionError('Notion source changed during verification. Inspect the workspace.', 'notion_stale')
        after = contract(result)
        if any(after.get(name) != value for name, value in previous.items()):
            raise service.NotionError('Existing schema differs on readback. Inspect Notion before another change.', 'notion_schema_verify')
        for prop in checked['properties']:
            actual = after.get(prop['name'], {})
            if actual.get('type') != prop['type']:
                raise service.NotionError('Notion did not confirm every new property type.', 'notion_schema_verify')
            if prop['type'] in ('select', 'multi_select') and [o.get('name') for o in actual['configuration'].get('options', [])] != prop['options']:
                raise service.NotionError('Notion option readback differs. Inspect the new property.', 'notion_schema_verify')
        return {'added_properties': [p['name'] for p in checked['properties']], 'verified': True,
                'source_id': source_id, 'title': 'Added Notion properties', 'message': 'Properties added. Record values were not changed.'}
