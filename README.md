# AWS Certificate Manager Cert Checker

aws-acm-cert-checker was created to allow more methods for alerting on expiring certificates managed by AWS Certificate Manager, and can be modified to alert at various different expiration intervals. This project may be very comparable to Amazon's own  [acm-certificate-expiration-check](https://docs.aws.amazon.com/config/latest/developerguide/acm-certificate-expiration-check.html) CloudFormation template.  The key differences as described later in this ReadMe are the different customizable methods.

Some key features are:
  - Ability to send alert notifications to SNS, email, or SMS
  - Ability to send alerts to PagerDuty
  - Set your own logic on expiration intervals and frequencies
  - Additional integrations can be added, such as sending notifications to Slack

#### Summary of files

`setup.cfg` can be ignored. It is a workaround needed only if you have a Homebrew-installed Python on Mac, which allows pip modules to be installed into a specific target directory.

`package-lambda-py.sh` is used to install pip requirements for the lambda function. It also packages up the lambda function as a `deployment.zip` file to be uploaded to AWS Lambda.

`lambda.py` is the logic of the lambda function. The lambda function will:
- Iterate through AWS ACM certificates in all regions (this can be fine-tuned by using an explicit list, if preferred)
- Create a detailed json payload describing important details of the certifcate
- Alert to either SNS or PagerDuty (defined by environment variable) when expiration is at 90 days, 60 days, 30 days, and then every day when there is 7 days left to expiration
- This lambda function was designed to run once per day

#### Creating the Lambda function
After the `package-lambda-py.sh` has been run, you will then need to upload the `deployment.zip` to AWS Lambda as a Python 2.7 function. For details, please see [how to upload the deployment.zip to AWS Lambda](https://forums.developer.amazon.com/questions/57536/how-to-upload-a-zip-deployment-package-to-lambda-u.html).  If you are just starting out, using the AWS Console UI is perfectly fine.  [Click here for a tutorial](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/RunLambdaSchedule.html) on how to trigger Lambda on a schedule (much like cron).

#### Setting Lambda environment variables
Next, you will need to set [environment variables for the lambda function](https://docs.aws.amazon.com/lambda/latest/dg/env_variables.html).
```ALERT_METHOD``` = ```SNS``` or ```PAGERDUTY```
```SNS_ARN``` = ```AWS_SNS_ARN_GOES_HERE``` (only set if SNS was selected)
```INTEGRATION_KEY``` = ```PAGERDUTY_INTEGRATION_KEY_GOES_HERE``` (only set if PAGERDUTY was selected)
