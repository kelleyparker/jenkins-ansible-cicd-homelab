import http.client
import json
from unittest.mock import MagicMock, Mock

import pytest

from scripts import smoke_test
from scripts.smoke_test import check_targets, fetch_build, inventory_targets


def inventory(hosts=None):
    return {
        'nginx': {'hosts': ['node1', 'node2'] if hosts is None else hosts},
        '_meta': {'hostvars': {
            'node1': {'ansible_host': '192.0.2.11', 'nginx_http_port': 8080},
            'node2': {'ansible_host': '192.0.2.12', 'nginx_http_port': '8081'},
        }},
    }


def test_targets_use_inventory_addresses_and_each_hosts_port():
    assert inventory_targets(inventory()) == [
        ('node1', '192.0.2.11', 8080), ('node2', '192.0.2.12', 8081),
    ]


def test_nested_groups_deduplicate_hosts_and_tolerate_cycles():
    data = inventory()
    data['nginx'] = {'hosts': ['node1'], 'children': ['rack']}
    data['rack'] = {'hosts': ['node1', 'node2'], 'children': ['nginx']}
    assert len(inventory_targets(data)) == 2


@pytest.mark.parametrize('data', [{}, inventory([])])
def test_missing_or_empty_group_cannot_pass(data):
    with pytest.raises(ValueError):
        inventory_targets(data)


@pytest.mark.parametrize('port', ['bad', 0, 65536])
def test_invalid_port_is_rejected(port):
    data = inventory()
    data['_meta']['hostvars']['node1']['nginx_http_port'] = port
    with pytest.raises(ValueError):
        inventory_targets(data)


@pytest.mark.parametrize('host', ['', 'host/path', 'user@host', 'host name'])
def test_invalid_host_is_rejected(host):
    data = inventory()
    data['_meta']['hostvars']['node1']['ansible_host'] = host
    with pytest.raises(ValueError):
        inventory_targets(data)


def test_every_one_of_ten_nodes_is_checked_even_after_a_failure():
    targets = [(f'node{i}', f'192.0.2.{i}', 8080) for i in range(1, 11)]
    fetch = Mock(side_effect=['old'] + ['42'] * 9)
    results = check_targets(targets, '42', attempts=1, fetch=fetch)
    assert len(results) == fetch.call_count == 10
    assert sum(result['passed'] for result in results) == 9
    assert not all(result['passed'] for result in results)


@pytest.mark.parametrize('response', ['41', '142', '<html>42</html>', ''])
def test_build_must_match_exactly(response):
    results = check_targets([('node', 'node', 8080)], '42', attempts=1,
                            fetch=Mock(return_value=response))
    assert not results[0]['passed']


@pytest.mark.parametrize('error', [OSError('offline'), TimeoutError(),
                                  ValueError('HTTP 500'), http.client.BadStatusLine('broken')])
def test_unreachable_or_invalid_response_fails(error):
    results = check_targets([('node', 'node', 8080)], '42', attempts=1,
                            fetch=Mock(side_effect=error))
    assert not results[0]['passed']


def test_transient_failure_is_retried_then_passes():
    fetch = Mock(side_effect=[OSError('reloading'), '41', '42'])
    sleep = Mock()
    result = check_targets([('node', 'node', 8080)], '42', attempts=3,
                           fetch=fetch, sleep=sleep)
    assert result[0]['passed']
    assert fetch.call_count == 3
    assert sleep.call_count == 2


def test_zero_targets_is_an_error():
    with pytest.raises(ValueError, match='zero targets'):
        check_targets([], '42')


@pytest.mark.parametrize('options', [{'attempts': 0}, {'timeout': 0}, {'delay': -1}])
def test_invalid_retry_settings_are_errors(options):
    with pytest.raises(ValueError):
        check_targets([('node', 'node', 8080)], '42', **options)


def test_http_response_is_read_and_connection_is_closed(monkeypatch):
    connection = MagicMock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.read.return_value = b'42\n'
    constructor = Mock(return_value=connection)
    monkeypatch.setattr(smoke_test.http.client, 'HTTPConnection', constructor)
    assert fetch_build('node', 8080, 5) == '42'
    constructor.assert_called_once_with('node', 8080, timeout=5)
    connection.close.assert_called_once()


def test_redirect_is_a_failure_not_a_success_from_another_node(monkeypatch):
    connection = MagicMock()
    connection.getresponse.return_value.status = 302
    connection.getresponse.return_value.read.return_value = b'42'
    monkeypatch.setattr(smoke_test.http.client, 'HTTPConnection', Mock(return_value=connection))
    with pytest.raises(ValueError, match='HTTP 302'):
        fetch_build('node', 8080, 5)
    connection.close.assert_called_once()


@pytest.mark.parametrize('build,expected_exit', [('42', 0), ('41', 1)])
def test_cli_exit_code_and_report(tmp_path, monkeypatch, build, expected_exit):
    inventory_file = tmp_path / 'inventory.json'
    report = tmp_path / 'smoke.json'
    inventory_file.write_text(json.dumps(inventory(['node1'])), encoding='utf-8')
    monkeypatch.setattr('sys.argv', [
        'smoke_test.py', '--inventory', str(inventory_file), '--expected-build', '42',
        '--attempts', '1', '--report', str(report),
    ])
    original = smoke_test.check_targets
    monkeypatch.setattr(smoke_test, 'check_targets',
                        lambda *args: original(*args, fetch=Mock(return_value=build)))
    assert smoke_test.main() == expected_exit
    assert json.loads(report.read_text(encoding='utf-8'))['results'][0]['passed'] == (expected_exit == 0)
