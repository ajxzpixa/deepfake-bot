import uuid, gzip, boto3
import datetime as dt
from bot import queries
from common.config import *


# Need to make this a background task
async def extract_and_analyze(ctx, user_mention, bot):
    await bot.wait_until_ready()

    extraction_id = str(uuid.uuid4().hex)
    text_file_name = f'./tmp/{extraction_id}-text.dsv.gz'
    channel_file_name = f'./tmp/{extraction_id}-channels.tsv.gz'

    channels = []
    timestamps = []
    message_counter = 0
    print(f'Extracting chat history for {user_mention}...')
    start_time = dt.datetime.now()
    with gzip.open(text_file_name, 'wb') as f:
        for channel in ctx.message.guild.channels:
            try:
                async for message in channel.history(limit=10**7):
                    if message.author == user_mention:
                        message_counter += 1
                        result = str(message.clean_content + unique_delimiter)
                        timestamps.append(int(message.created_at.timestamp()))
                        channels.append(channel.name)
                        f.write(result.encode())
            except Exception:
                continue

    with gzip.open(channel_file_name, 'wb') as f:
        f.write('timestamp,channel\n'.encode())
        for i in range(len(channels)):
            f.write(f'{timestamps[i]},{channels[i]}\n'.encode())

    end_time = dt.datetime.now()
    print(f'{message_counter} messages extracted.')
    print(f'Logs copied to tmp folder. Time elapsed = {end_time - start_time}')

    # S3
    print('Uploading to S3...')
    start_time = dt.datetime.now()
    upload_to_s3(text_file_name)
    upload_to_s3(channel_file_name)
    end_time = dt.datetime.now()
    print(f'Files uploaded to S3: {extraction_id}. Time elapsed = {end_time - start_time}')

    # Add to database
    queries.create_dataset(ctx, user_mention, extraction_id)

    # Cleanup local disk
    os.remove(text_file_name)
    os.remove(channel_file_name)

    # Bot reply
    await ctx.message.channel.send(f'Analysis complete for {user_mention}. Found {message_counter} messages.')


def upload_to_s3(file_name):
    s3 = boto3.resource('s3',
                        aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key)

    s3.Object(aws_s3_bucket_prefix, f'{file_name}'.strip('./tmp/')).upload_file(f'{file_name}')
