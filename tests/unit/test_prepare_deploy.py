import json

import pytest

from scripts.prepare_deploy import deployment_vars


@pytest.fixture
def content(tmp_path):
    folder = tmp_path / 'website with spaces'
    folder.mkdir()
    (folder / 'index.html').write_text('<h1>Lab</h1>', encoding='utf-8')
    return folder


def test_build_metadata_survives_json_and_paths_with_spaces(content):
    variables = json.loads(json.dumps(deployment_vars('42', content)))
    assert variables == {
        'nginx_build_number': '42',
        'nginx_content_dir': str(content.resolve()),
    }


@pytest.mark.parametrize('build', ['', '-1', '42 other=value', 'x', '1\n', '１２'])
def test_invalid_build_cannot_be_injected_into_nginx(build, content):
    with pytest.raises(ValueError, match='ASCII digits'):
        deployment_vars(build, content)


def test_missing_website_fails_before_contacting_any_target(tmp_path):
    with pytest.raises(ValueError, match='Missing website'):
        deployment_vars('42', tmp_path)
