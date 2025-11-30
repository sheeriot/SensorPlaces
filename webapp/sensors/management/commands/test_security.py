import subprocess
import requests
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Test URL access and logging behavior'

    def add_arguments(self, parser):
        parser.add_argument('target', type=str, nargs='?', default='https://austinvoicedata.com', help='Target URL base')

    def handle(self, *args, **options):
        base_url = options['target']
        self.stdout.write(f"Testing security rules against {base_url}")

        tests = [
            # (path, expected_status_code_or_exception, description)
            ('/System/CommandAndCGIScripts', 403, 'Block System path'),
            ('/test.php', 403, 'Block PHP files'),
            ('/wp-admin/login.php', 403, 'Block WP Admin'),
            ('/.env', 403, 'Block .env files'),
            ('/test.jar', 403, 'Block JAR files'),
            ('/+CSCOE+/logon.html', 403, 'Block Cisco VPN probe'),
            ('/?cover=print;sortcol=0', 403, 'Block complex query strings'),
            ('/', 200, 'Allow Homepage'),
            ('/css/themes/blue.min.css', 200, 'Allow Static Files'),
        ]

        for path, expected, description in tests:
            url = f"{base_url}{path}"
            self.stdout.write(f"Testing: {description} ({path})")

            try:
                # We need to use verify=False for self-signed or local dev certs if strictly needed,
                # but assume valid certs for production-like testing.
                # However, since we return 444 (Close Connection), requests should raise an exception.
                response = requests.get(url, verify=False, timeout=5)
                status = response.status_code
            except requests.exceptions.ConnectionError:
                status = 'ConnectionError'
            except requests.exceptions.ChunkedEncodingError:
                # Sometimes 444 appears as this
                status = 'ConnectionError'
            except Exception as e:
                status = str(e)

            if expected == 'ConnectionError':
                # Accept ConnectionError OR empty response which might look like different things depending on client
                if status == 'ConnectionError' or status == 444:
                    self.stdout.write(self.style.SUCCESS(f"  [PASS] Request blocked as expected ({status})"))
                else:
                    self.stdout.write(self.style.ERROR(f"  [FAIL] Expected block, got {status}"))
            else:
                if status == expected:
                    self.stdout.write(self.style.SUCCESS(f"  [PASS] Request allowed as expected ({status})"))
                else:
                    self.stdout.write(self.style.ERROR(f"  [FAIL] Expected {expected}, got {status}"))

        self.stdout.write("\nNOTE: Check security_violations.log manually to verify blocks were logged.")
