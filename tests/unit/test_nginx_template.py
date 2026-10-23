from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def test_template_preserves_nginx_variables_and_embeds_current_build():
    template_dir = Path(__file__).resolve().parents[2] / 'roles/nginx/templates'
    environment = Environment(loader=FileSystemLoader(template_dir), undefined=StrictUndefined)
    rendered = environment.get_template('nginx.conf.j2').render(
        nginx_build_number='42', nginx_http_port=8080,
    )
    assert 'return 200 "42\\n";' in rendered
    assert 'listen 8080 default_server;' in rendered
    assert 'try_files $uri $uri/ =404;' in rendered
