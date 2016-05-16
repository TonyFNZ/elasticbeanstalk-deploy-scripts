#! /usr/bin/env python
import sys, boto3, argparse, logging, time

# Globals
EB = boto3.client('elasticbeanstalk')
logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s - %(message)s', level=logging.INFO)
LOG = logging.getLogger('eb-deploy')
# Hide annoying log messages
logging.getLogger('botocore.vendored.requests.packages.urllib3.connectionpool').setLevel(logging.WARNING)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Deploy an existing EB application version to an existing environment',
        epilog='''Known limitation:
            Single instance environments may report a failure if a \'Rolling' deployment is used.
            This is due to the environment health not remaining green when there are 0 active instances.
            The workaround is to use a \'Rolling with additional batch\' deployment to keep the environment green.'''
    )
    parser.add_argument('-a','--application-name', required=True,
                    help='The EB application which owns the target environment')
    parser.add_argument('-e','--environment-name', required=True,
                    help='The EB environment which should be updated')
    parser.add_argument('-v','--version-label', required=True,
                    help='The EB application version which should be applied to the environment')
    args = parser.parse_args();

    perform_environment_update(
        args.application_name,
        args.environment_name,
        args.version_label
    )
    return


# -----------------------------------------------------------------------------
# Update the specified environment to the specified version
# Wait for the update to complete and log environment events
# Wait to ensure the environment stays health for a time
# -----------------------------------------------------------------------------
def perform_environment_update(application, environment, version):
    LOG.info('Updating environment %s to version %s', environment, version)

    environment_id, request_id = update_environment_to_version(application, environment, version)
    LOG.info('Update has been requested: %s', request_id)


    logged_events = [] # to avoid logging the same event twice

    wait_for_ready_status(environment_id, request_id, logged_events)
    # Ready status means the update has been completed
    LOG.info('Environment update has been completed')

    duration = 60 # How long we should monitor environment health for
    LOG.info('Will now monitor environment health for %d seconds', duration)

    result = monitor_env_health(environment_id, version, duration, request_id, logged_events)
    if not result:
        LOG.error('Release Failed!')
        sys.exit(1)
    else:
        LOG.info('Release Complete!')
    return

# -----------------------------------------------------------------------------
# Update Environment to the Specified Version
# -----------------------------------------------------------------------------
def update_environment_to_version(application, environment, version):
    response = EB.update_environment(
        ApplicationName=application,
        EnvironmentName=environment,
        VersionLabel=version
    )
    LOG.debug(response)

    environment_id = response['EnvironmentId']
    request_id = response['ResponseMetadata']['RequestId']
    return (environment_id, request_id)

# -----------------------------------------------------------------------------
# Get Environment Details
# -----------------------------------------------------------------------------
def get_env_details(environment_id):
    response = EB.describe_environments(
        EnvironmentIds=[ environment_id ],
        IncludeDeleted=False
    )
    details = response['Environments'][0]
    return details

def get_env_status(environment_id):
    details = get_env_details(environment_id)
    status = details['Status']
    return status

def get_env_health(environment_id):
    details = get_env_details(environment_id)
    health = details['Health']
    return health


# -----------------------------------------------------------------------------
# Wait for environment to reach 'Ready' status
# 'Ready' means the environment update has completed
# -----------------------------------------------------------------------------
def wait_for_ready_status(environment_id, request_id, logged_events):

    # TODO implement a timeout failure
    while 1:
        # Log environment update events while we wait for Ready status
        log_new_events(request_id, logged_events)

        current_status = get_env_status(environment_id)
        LOG.debug('Current environment status is %s', current_status)

        if current_status == 'Ready':
            LOG.info('Environment status transition to \'Ready\' completed')
            break
        else:
            time.sleep(15)
    return


# -----------------------------------------------------------------------------
# Log events which have not been logged before
# -----------------------------------------------------------------------------
def log_new_events(request_id, logged_events):
    response = EB.describe_events(
        RequestId=request_id,
        Severity='INFO'
    )
    events = response['Events'] # Note, events come newest first

    for event in reversed(events):
        if event in logged_events:
            continue

        LOG.info('... %s [%s] %s', event['EventDate'].strftime('%H:%M:%S'), event['Severity'], event['Message'])
        logged_events.append(event)
    return


# -----------------------------------------------------------------------------
# Check that the release was successful
# Checks version is correct and then monitors environment health for a time
# -----------------------------------------------------------------------------
def monitor_env_health(environment_id, version, duration, request_id, logged_events):
    cutoff = time.time() + duration

    result = check_env_version(environment_id, version, cutoff, request_id, logged_events)
    if not result:
        return;

    result = ensure_env_health_green(environment_id, cutoff, request_id, logged_events)
    return result

# -----------------------------------------------------------------------------
# Check environment version is the one we expected
# It may be different if EB automatically rolled back a failed update
# -----------------------------------------------------------------------------
def check_env_version(environment_id, version, cutoff, request_id, logged_events):

    # Wait for health to be non-grey before checking version
    while True:
        # Log new events while we wait
        log_new_events(request_id, logged_events)

        details = get_env_details(environment_id)
        current_health = details['Health']
        if current_health != 'Grey':
            LOG.debug('Have reached a non-grey health (%s)', current_health)

            current_version = details['VersionLabel']
            if current_version != version:
                LOG.error('Version after upgrade did not match expected version (%s)', current_version)
                return False
            else:
                return True

        if time.time() > cutoff:
            LOG.error('Failed to reach non-grey health before cutoff')
            return False
        else:
            time.sleep(15)
    return

# -----------------------------------------------------------------------------
# Monitor environment health for the specified duration
# This helps to ensure the new version doesn't fail soon after deployment
# -----------------------------------------------------------------------------
def ensure_env_health_green(environment_id, cutoff, request_id, logged_events):

    while True:
        # Log new events while we wait (should be none unless something goes wrong)
        log_new_events(request_id, logged_events)

        health = get_env_health(environment_id)
        if health != 'Green':
            LOG.error('Environment health is not \'Green\' after update (%s)', health)
            return False

        LOG.info('... Environment health is Green')

        if time.time() > cutoff:
            break
        else:
            time.sleep(15)

    LOG.info('Monitoring complete.  Environment is healthy')
    return True


if __name__ == "__main__":
    main()
