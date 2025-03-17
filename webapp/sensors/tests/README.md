# Sensors App Tests

This directory contains tests for the Sensors Django application. The tests are organized to cover different aspects of the application:

## Test Files

- `test_views.py`: Tests for basic view functionality
- `test_urls.py`: Tests for URL routing and access
- `test_js_interactions.py`: Tests for JavaScript interactions using Selenium

## Fixtures

Fixture files are stored in the `fixtures/` directory and are used to provide test data. To generate fixtures from your current database, run:

```bash
python sensors/tests/generate_fixtures.py
```

This will create JSON fixture files for:
- Users
- Places
- Locations
- Devices
- Sensors
- Sensor Readings

## Running Tests

### Basic Tests

To run all tests:

```bash
python manage.py test sensors
```

To run a specific test file:

```bash
python manage.py test sensors.tests.test_urls
```

To run a specific test class:

```bash
python manage.py test sensors.tests.test_urls.URLResolveTestCase
```

To run a specific test method:

```bash
python manage.py test sensors.tests.test_urls.URLResolveTestCase.test_place_urls_resolve
```

### JavaScript Interaction Tests

The JavaScript interaction tests use Selenium and require:
1. Selenium package: `pip install selenium`
2. A compatible webdriver (Chrome, Firefox, etc.)
3. The development server running

These tests are skipped by default. To run them:

1. Start the development server:
   ```bash
   python manage.py runserver
   ```

2. In another terminal, run the tests after removing the `@unittest.skip` decorator from the test methods you want to run.

## Test-Driven Development

For new features, consider writing tests first:

1. Write a test that defines the expected behavior
2. Run the test to see it fail
3. Implement the feature
4. Run the test again to see it pass
5. Refactor as needed

## Coverage

To check test coverage:

1. Install coverage: `pip install coverage`
2. Run tests with coverage: `coverage run --source='sensors' manage.py test sensors`
3. Generate a report: `coverage report`
4. For a detailed HTML report: `coverage html` (then open `htmlcov/index.html`) 