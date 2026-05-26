import aws_cdk as cdk
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy

app = cdk.App()
stack = cdk.Stack(app, "HskVocabularyDeployment")

bucket = s3.Bucket.from_bucket_name(stack, "VocabBucket", "daily-dragon-bucket")

s3deploy.BucketDeployment(
    stack,
    "HskFiles",
    sources=[s3deploy.Source.asset("../hsk/json")],
    destination_bucket=bucket,
    destination_key_prefix="hsk",
)

app.synth()