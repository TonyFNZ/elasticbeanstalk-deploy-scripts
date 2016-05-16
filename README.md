# Elastic Beanstalk Deployments
A collection of scripts which provide reliable and robust deployments of new application versions into AWS Elastic Beanstalk.
The key benefit (over and above the awscli) is that these scripts monitor the outcome of the deployment to ensure it is
successful.

These scripts are tool chain agnostic and can be used with your facourite CI/CD tool.  They have been specifically tested
with Jenkins and Bamboo.

Note, these scripts require Python to be installed aswell as boto3 (the AWS SDK for Python).  Python is available by default
on most Linux distros, but you will likely need to install boto3 using the command below:
```
sudo pip install boto3
```

## publish.py
This script will:
 * Upload your application package to S3
 * Create a new `Application Version` within your application
 
> Note, it is up to you to create an application package which is right for the Elastic Beanstalk 
> platform you are using.  Eg. Tomcat applications accept a war file, other application types
> accept a zip file, etc.

```
usage: publish.py [-h] -a APPLICATION_NAME -v VERSION_LABEL 
                  [-d VERSION_DESCRIPTION] -b S3_BUCKET -f PACKAGE_FILE


arguments:
  -h, --help            show this help message and exit
  -a APPLICATION_NAME, --application-name APPLICATION_NAME
                        The EB application which owns the target environment
  -v VERSION_LABEL, --version-label VERSION_LABEL
                        The name (label) of the new version to create
  -d VERSION_DESCRIPTION, --version-description VERSION_DESCRIPTION
                        The description of the new version to create
  -b S3_BUCKET, --s3-bucket S3_BUCKET
                        The S3 bucket to store the software package into
  -f PACKAGE_FILE, --package-file PACKAGE_FILE
                        The local software package file to publish
```

## deploy.py
This script will:
 * Initiate the upgrade of the target environment to the specified application version
 * Monitor the upgrade process till it is complete and log environment events as they occur
 * Verify the final application version matches the requested version
 * Verify that the environment stays healthy after the upgrade
 * Only returns successfully when the upgrade is successful and the environment remains healthy
 
```
usage: deploy.py [-h] -a APPLICATION_NAME -e ENVIRONMENT_NAME -v VERSION_LABEL

arguments:
  -h, --help            show this help message and exit
  -a APPLICATION_NAME, --application-name APPLICATION_NAME
                        The EB application which owns the target environment
  -e ENVIRONMENT_NAME, --environment-name ENVIRONMENT_NAME
                        The EB environment which should be updated
  -v VERSION_LABEL, --version-label VERSION_LABEL
                        The EB application version which should be applied to
                        the environment
```
Known limitation: Single instance environments may report a failure if a `Rolling` deployment is used. 
This is due to the environment health not remaining `Green` during the deployment. The workaround is 
to use a `Rolling with additional batch` which keeps the environment healthy during the deployment.
