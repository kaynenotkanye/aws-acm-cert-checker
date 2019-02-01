#!/usr/bin/python
import os
import pypd
import boto3
import logging
import json
import datetime

from botocore.exceptions import ClientError

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)
logger.info('Starting...')

alert_method = os.environ['ALERT_METHOD']  ### Right now this lambda only supports "SNS" or "PAGERDUTY"

def awk_like(instring, index, delimiter=":"):  ### This is an 'awk' like function used to extract data from AWS arns
  try:
    return [instring,instring.split(delimiter)[index-1]][max(0,min(1,index))]
  except:
    return ""

### Send alert notifications based on ALERT_METHOD environment variable of the lambda
def send_notification(detailed_message, summarized_message):
    if (alert_method == "SNS"):
        sns_publish(detailed_message, summarized_message)
    elif (alert_method == "PAGERDUTY"):
        send_pagerduty_event(detailed_message, summarized_message)
    else:
        logger.exception("The environment variable for ALERT_METHOD must either be: SNS or PAGERDUTY")

### Publish to SNS topic based on SNS_ARN environment variable
def sns_publish(detailed_message, summarized_message):
    logger.warn(summarized_message)
    sns_arn = os.environ['SNS_ARN']
    sns_region = awk_like(sns_arn, 4)   ### Extract the region from the provided arn
    sns = boto3.client('sns', region_name=sns_region) ### We only need to publish to 1 sns topic
    response = sns.publish(
      TargetArn=sns_arn,
      Message=json.dumps({
        'default': json.dumps(detailed_message, sort_keys=True, indent=4),
        #'sms': 'We can customize sms messages here...'
        #'email': 'We can customize email messages here...otherwise, using "default" is fine too'
        }),
      Subject=summarized_message,
      MessageStructure='json'
    )

### Send event through PagerDuty api based on INTEGRATION_KEY environment variable
def send_pagerduty_event(detailed_message, summarized_message):
    # Create a PagerDuty Version2 event
    pypd.EventV2.create(data={
        'routing_key': os.environ['INTEGRATION_KEY'],  ### This is the routing Integration_Key from PagerDuty
        'event_action': 'trigger',
        'payload': {
            'summary': summarized_message,
            'custom_details': detailed_message,
            'severity': 'error',
            'source': 'PagerDuty api',
        }
    })

### This function creates a json with the details of AWS certificates
def create_json(acm, array_of_arns):
    data = {}
    # Find the total number of ISSUED certificates
    number_of_certs = len(array_of_arns)
    todays_date = datetime.date.today()
    # Iterate through the AWS ACM certificates and create a detailed json payload of the certificate
    for i in xrange(number_of_certs):
        r = acm.describe_certificate(CertificateArn=array_of_arns[i])
        expires_on = ((r['Certificate']['NotAfter']).date())
        issued_on = ((r['Certificate']['NotBefore']).date())
        aws_account = awk_like(r['Certificate']['CertificateArn'], 5)
        domain_name = r['Certificate']['DomainName']
        data['AwsAccount'] = aws_account
        data['AwsRegion'] = awk_like(r['Certificate']['CertificateArn'], 4)
        certificate_arn = r['Certificate']['CertificateArn']
        data['CertificateArn'] = certificate_arn
        data['DomainName'] = domain_name
        data['DomainNameAlternatives'] = r['Certificate']['SubjectAlternativeNames']
        data['Status'] = r['Certificate']['Status']
        data['Type'] = r['Certificate']['Type']
        data['RenewalEligibility'] = r['Certificate']['RenewalEligibility']
        data['Issuer'] = r['Certificate']['Issuer']
        data['IssuedOn'] = issued_on.strftime("%Y-%m-%d")
        data['ExpiresOn'] = expires_on.strftime("%Y-%m-%d")
        summarized_message = "Certificate %s is expiring on %s in AWS account: %s" % (domain_name, expires_on, aws_account)
        data['CustomMessage'] = summarized_message
        diff = expires_on - todays_date
        expire_in = diff.days

        ### Set alerts at 90 days, 60 days, 30 days, and every day for week leading up to expiration
        if (expire_in == 90):
            send_notification(data, summarized_message) # data is the full json details, summarized_message is the short tldr message
        elif (expire_in == 60):
            send_notification(data, summarized_message)
        elif (expire_in == 30):
            send_notification(data, summarized_message)
        elif (expire_in <= 7 and expire_in >= 0):
            send_notification(data, summarized_message)
        elif (expire_in < 0):
            logger.warn("%s has expired %d day(s) ago." % (certificate_arn, expire_in))
        else:
            logger.info("%s will expire in %d day(s)." % (certificate_arn, expire_in))

def lambda_handler(event, context):
    #list_of_regions = ['us-west-2', 'us-east-1']  ### List of regions to check for AWS ACM --
    ### Not currently used but kept in as an option. Use this only if you want to manually maintain a list of specific regions to cycle through
    logger.info("lambda_handler starting...")
    function_arn = str(context.invoked_function_arn)
    default_region = awk_like(function_arn, 4)
    logger.info("functionArn: %s" % function_arn)

    ec2 = boto3.client('ec2', region_name=default_region)  # This is used to lookup available regions
    list_of_regions = [region['RegionName'] for region in ec2.describe_regions()['Regions']]

    for x in list_of_regions:
        array_of_arns = []
        acm = boto3.client('acm', region_name=x)
        resp = acm.list_certificates(CertificateStatuses=['ISSUED'])
        ### The following prints 'normal' json.  This snippet is left in just in case you need it for troubleshooting purposes.
        #json_object = json.dumps(resp)
        #print(json_object)

        ### Looking at the content_length from the metadata to determine if ACM certificates exist in a particular region
        ### This is used for regions that do not have any imported ACM certificates
        ### If this method is not preferred, you may define a list_of_regions as defined above
        content_length = resp['ResponseMetadata']['HTTPHeaders']['content-length']
        if (int(content_length) < 50):
            logger.info("The response metadata has detected a content-length that indicates that there are no ACM certificates in the current region: %s" % x)
        else:
            ### Iterate through the entire array of arns and do not error if out of range is reached
            try:
                for i in xrange(99):   ### Maximum range of 99 certificates has been set here for AWS ACM, adjustable if you have more...
                    array_of_arns.append(resp['CertificateSummaryList'][i]['CertificateArn'])
            except IndexError:
                pass

                create_json(acm,array_of_arns)
