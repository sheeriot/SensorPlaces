import os
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Run beta tests by setting RUN_BETA_TESTS=true environment variable.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--failfast',
            action='store_true',
            help='Stop running the tests after the first failure',
        )

    def handle(self, *args, **options):
        os.environ['RUN_BETA_TESTS'] = 'true'
        self.stdout.write(self.style.SUCCESS("Running Beta Tests..."))

        test_args = ['sensors']
        if options['failfast']:
            test_args.append('--failfast')

        call_command('test', *test_args)
