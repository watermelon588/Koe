from koe import action_display as view


def test_calendar_recurrence_is_readable_and_never_claims_meet_ready():
    display = view.describe('calendar_upsert_event', {
        'title': 'Weekly sync', 'start': '2026-10-19T10:00:00+05:30',
        'end': '2026-10-19T10:30:00+05:30', 'expected_timezone': 'Asia/Kolkata',
        'recurrence': {'frequency': 'weekly', 'interval': 1, 'count': 4}, 'create_meet': True,
        'attendees': ['teammate@example.com'], 'token': 'private-secret',
    })
    assert display['title'] == 'Create Weekly sync'
    assert '10:00–10:30' in display['lines'][0] and 'Asia/Kolkata' in display['lines'][0]
    assert 'Every week · 4 times' in display['lines']
    assert any('Request a Google Meet' in line for line in display['lines'])
    assert len(display['lines']) <= 4 and 'private-secret' not in str(display)
    assert 'RRULE' not in str(display) and 'dateTime' not in str(display)


def test_all_day_end_is_displayed_inclusively():
    display = view.describe('calendar_upsert_event', {
        'title': 'Away', 'start': '2026-10-19', 'end': '2026-10-21', 'all_day': True,
    })
    assert '19 Oct 2026–20 Oct 2026' in display['lines'][0]
    assert 'All day' in display['lines'][0]


def test_cancellation_uses_frozen_event_and_explicit_scope():
    display = view.describe('calendar_cancel_event', {
        'scope': 'series', 'approved_event': {'title': 'Standup',
            'start': {'dateTime': '2026-10-19T10:00:00+05:30'},
            'end': {'dateTime': '2026-10-19T10:30:00+05:30'}},
    })
    assert display['title'] == 'Cancel Standup'
    assert any('whole series' in line for line in display['lines'])


def test_sheets_previews_bound_text_and_use_provider_links_only():
    display = view.describe('sheets_add_columns', {
        'columns': ['Billable'], 'sheet_name': 'Timesheet', 'spreadsheet_id': 'sheet-123',
        'access_token': 'secret',
    })
    assert display['title'] == 'Add column Billable'
    assert display['url'] == 'https://docs.google.com/spreadsheets/d/sheet-123/edit'
    assert 'Timesheet' in ' '.join(display['lines']) and 'secret' not in str(display)
    entry = view.describe('sheets_log_hours', {'hours': 2.5, 'client': 'Acme',
        'date': '2026-10-16', 'note': 'x' * 5000, 'spreadsheet_id': 'bad/../../id'})
    assert entry['title'] == 'Log 2.5 hours · Acme'
    assert all(len(line) <= 320 for line in entry['lines']) and entry['url'] == ''


def test_public_pending_keeps_full_audit_and_omits_execution_data():
    action = {'id': 'a', 'summary': 'Full audit\n' + 'x' * 4000, 'expires_ts': '2099-01-01',
              'tool': 'github_comment', 'args_json': {'repo': 'me/app', 'number': 42,
                  'body': 'Please add tests', 'secret': 'private'}, 'owner_id': 'owner'}
    public = view.pending(action)
    assert public['summary'] == action['summary']
    assert public['display']['title'] == 'Comment on me/app #42'
    assert public['display']['url'] == 'https://github.com/me/app/pull/42'
    assert set(public) == {'id', 'summary', 'expires_ts', 'display'}
    assert view.pending(None) is None


def test_links_reject_credentials_ports_and_unrelated_hosts():
    for value in ['javascript:alert(1)', 'https://docs.google.com.evil.test/x',
                  'https://user:secret@docs.google.com/x', 'https://docs.google.com:444/x']:
        assert view.safe_link(value) == ''
    assert view.safe_link('https://notion.so/page') == 'https://notion.so/page'
