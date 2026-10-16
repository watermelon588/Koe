"""Resolve user-supplied artist/title against a granted playlist, outside AI context."""
import asyncio
import re
import secrets
import unicodedata

from koe import spotify_service as sp


def normal(value):
    text = unicodedata.normalize('NFKD', str(value).casefold().replace('$', 's'))
    return ' '.join(re.sub(r'[^\w]+', ' ', ''.join(c for c in text if not unicodedata.combining(c))).split())


def choose(items, *, artist=None, title=None):
    artist, title = normal(artist or ''), normal(title or '')
    matches, exact, unavailable = [], [], False
    for position, item in items:
        track = sp.track(item)
        artists = [normal(name) for name in track['artists']]
        name = normal(track['name'])
        if artist and not any(artist == value or f' {artist} ' in f' {value} ' for value in artists):
            continue
        if title and title != name and f' {title} ' not in f' {name} ':
            continue
        if not track['playable']:
            unavailable = True
            continue
        matches.append((position, track['uri']))
        if title and title == name:
            exact.append((position, track['uri']))
    matches = exact or matches
    # Repeated copies of the same recording are not an ambiguous title.
    unique = list({uri: position for position, uri in reversed(matches)}.items())
    if not unique:
        return {'state': 'unavailable' if unavailable else 'not_found'}
    if title and len(unique) > 1:
        return {'state': 'ambiguous'}
    _, position = secrets.choice(unique) if not title else unique[0]
    return {'state': 'matched', 'position': position}


async def resolve(owner, generation, *, artist=None, title=None):
    before = await sp.selected(owner, generation)
    items, offset = [], 0
    # No background scanning or persistent catalog: read only for an explicit request.
    try:
        async with asyncio.timeout(15):
            while True:
                data = await sp.request(owner, 'GET', '/playlists/' + before['id'] + '/items',
                                        generation=generation, params={'offset': offset, 'limit': 50})
                page = sp.page(data, offset, 50, lambda item: item)
                for index, item in enumerate(page['items'], offset):
                    items.append((index, item.get('item', item.get('track')) if isinstance(item, dict) else None))
                if page['next_offset'] is None:
                    break
                offset = page['next_offset']
                if offset >= 5000:
                    raise sp.SpotifyError('spotify_selection_incomplete', message='Playlist scanning could not finish. Use the visible track list.')
            after = await sp.selected(owner, generation)
            if before['snapshot_id'] != after['snapshot_id']:
                raise sp.SpotifyError('spotify_playlist_stale')
    except TimeoutError:
        raise sp.SpotifyError('spotify_selection_incomplete', message='Playlist scanning timed out. No playback was requested.') from None
    result = choose(items, artist=artist, title=title)
    return {**result, 'snapshot_id': after['snapshot_id']}
