docker compose run --rm test ./manage.py test aidrequests.tests.test_views

docker compose run --rm test ./manage.py test sensors.tests.test_views.SensorsViewTestCase.test_sensor_update_view --failfast

docker compose run --rm test ./manage.py test sensors.tests.test_views.SensorsViewTestCase.test_sensor_update_post --failfast

docker compose run --rm test ./manage.py test sensors.tests.test_influx_integration
