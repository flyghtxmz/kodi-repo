"""Small local collection and search history, independent of disposable caches."""
import json
import os
import tempfile
from local_cache import directory


def read():
    root = directory()
    if root is None:
        return {}
    try:
        path = root.parent / 'user_state.json'
        if path.stat().st_size > 200_000:
            return {}
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def write(data):
    root = directory()
    if root is None:
        raise OSError('Perfil Kodi indisponível')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root.parent, delete=False) as f:
            temporary = f.name
            json.dump(data, f, ensure_ascii=False)
        os.replace(temporary, root.parent / 'user_state.json')
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def remember_search(term, media):
    data = read()
    history = data.get('searches') or []
    item = {'term': term[:80], 'media': media}
    data['searches'] = [item] + [x for x in history if x != item][:19]
    write(data)


def toggle_favorite(movie):
    data = read()
    favorites = data.get('favorites') or []
    key = (movie['id'], movie['type'])
    exists = any((x.get('id'), x.get('type')) == key for x in favorites)
    favorites = [x for x in favorites if (x.get('id'), x.get('type')) != key]
    if not exists:
        favorites.insert(0, {field: movie.get(field, '') for field in ('id', 'type', 'title', 'poster')})
    data['favorites'] = favorites[:200]
    write(data)
    return not exists
