import datetime
import os

import boto3
import nest
import logging
import time
# https://forecast-v3.weather.gov/documentation

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

NAMESPACE = 'pynestaws'
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')
access_token_cache_file = 'nest.json'
cloudwatch_client = boto3.client('cloudwatch')


def _sanitize(metric_name, metric_value):
    return {
        'fanStatus': {
            True: 1,
            False: 0
        },
        'hasLeaf': {
            True: 1,
            False: 0
        },
        'hvacState': {
            'cooling': -1,
            'heating': 1,
            'off': 0
        },
        'mode': {
            'heat-cool': 10,
            'eco': -10,
            'cool': -1,
            'heat': 1,
            'off': 0
        },
        'online': {
            True: 1,
            False: 0
        }
    }.get(metric_name, {}).get(metric_value, metric_value)
    pass


def _get_unit_from_metric_name(metric_key):
    return {
        'indoorHumidity': 'Percent'
    }.get(metric_key, 'None')


def put_cloudwatch_metrics(all_data):
    for structure_name in all_data:
        structure = all_data[structure_name]
        metric_data = []
        for metric_key, metric_value in structure['nestData'].items():
            metric_data.append({
                'MetricName': metric_key,
                'Dimensions': [
                    {
                        'Name': 'structureName',
                        'Value': structure['structureName']
                    }
                ],
                'Timestamp': structure['timestamp'],
                'Value': _sanitize(metric_key, metric_value),
                'Unit': _get_unit_from_metric_name(metric_key)
            })
        for metric_key, metric_value in structure['weatherData'].items():
            metric_data.append({
                'MetricName': metric_key,
                'Dimensions': [
                    {
                        'Name': 'structureName',
                        'Value': structure['structureName']
                    }
                ],
                'Timestamp': structure['timestamp'],
                'Value': _sanitize(metric_key, metric_value),
                'Unit': _get_unit_from_metric_name(metric_key)
            })
        cloudwatch_client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=metric_data
        )


def get_weather_data(zipcode):
    return {}


def parse_nest_data(thermostats):
    all_data = {}
    for thermostat in thermostats:
        logger.info('Found Thermostat Name: {}'.format(thermostat.name_long))
        zip_code = thermostat.postal_code
        nest_data = {
            'fanStatus': thermostat.fan,
            'hasLeaf': thermostat.has_leaf,
            'indoorHumidity': thermostat.humidity,
            'hvacState': thermostat.hvac_state,
            'mode': thermostat.mode,
            'online': thermostat.online,
            'targetTemperature': thermostat.target,
            'indoorTemperature': thermostat.temperature
        }

        weather_data = get_weather_data(zip_code)

        all_data[thermostat.name_long.title().strip()] = {
            'nestData': nest_data,
            'weatherData': weather_data,
            'structureName': ''.join([i for i in thermostat.name_long if i.isalpha()]),
            'timestamp': datetime.datetime.utcnow()
        }

    return all_data


def lambda_handler(event, context):
    nest_api = nest.Nest(client_id=client_id, client_secret=client_secret,
                         access_token_cache_file=access_token_cache_file)

    if nest_api.authorization_required:
        print('Go to ' + nest_api.authorize_url + ' to authorize, then enter PIN below')
        pin = input("PIN: ")
        nest_api.request_token(pin)

    data = parse_nest_data(nest_api.thermostats)
    put_cloudwatch_metrics(data)

if __name__ == "__main__":
    # execute only if run as a script
    while True:
        lambda_handler(None, None)
        print('Done')
        time.sleep(60)
