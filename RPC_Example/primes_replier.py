#
# (c) 2023 Copyright, Real-Time Innovations, Inc.  All rights reserved.
#
# RTI grants Licensee a license to use, modify, compile, and create derivative
# works of the Software solely for use with RTI products.  The Software is
# provided "as is", with no warranty of any type, including any warranty for
# fitness for any purpose. RTI is under no obligation to maintain or support
# the Software.  RTI shall not be liable for any incidental or consequential
# damages arising out of the use or inability to use the software.
#

import argparse
import math
from typing import Sequence, Tuple

import rti.connextdds as dds
from rti.rpc import Replier
import Primes


class MyDataReaderListener(dds.DataReaderListener):
    def on_sample_rejected(self, reader, status):
        print("Sample rejected!")
        print(f"  Reason: {status.last_reason}")
        print(f"  Total count: {status.total_count}")
        print(f"  Total count change: {status.total_count_change}")

    def on_subscription_matched(self, reader, status):
        print("Subscription matched!")
        print(f"  Current count: {status.current_count}")
        print(f"  Total count: {status.total_count}")

    def on_sample_lost(self, reader, status):
        print("Sample lost!")
        print(f"  Total count: {status.total_count}")
        print(f"  Total count change: {status.total_count_change}")

    def on_requested_deadline_missed(self, reader, status):
        print("Requested deadline missed!")
        print(f"  Total count: {status.total_count}")
        print(f"  Total count change: {status.total_count_change}")

    def on_requested_incompatible_qos(self, reader, status):
        print("Requested incompatible QoS!")
        print(f"  Total count: {status.total_count}")
        print(f"  Last policy ID: {status.last_policy_id}")

def is_prime(val):
    if val <= 1:
        return False
    if val == 2:
        return True
    if val > 2 and val % 2 == 0:
        return False

    max_div = int(math.floor(math.sqrt(val)))
    for i in range(3, 1 + max_div, 2):
        if val % i == 0:
            return False
    return True


def hex_string_to_octet_param(hex_str):
    if len(hex_str) != 32:
        raise ValueError("instance_handle string must be 32 hex characters")
    return " ".join("0x" + hex_str[i:i+2] for i in range(0, 32, 2))

def hex_string_to_octet_param_no_prefix(hex_str):
    if len(hex_str) != 32:
        raise ValueError("instance_handle string must be 32 hex characters")
    return " ".join(hex_str[i:i+2] for i in range(0, 32, 2))

def calculate_and_send_primes(
    replier: Replier,
    request: Primes.PrimeNumberRequest,
    request_info: dds.SampleInfo,
):
    n = request.n
    primes_per_reply = request.primes_per_reply

    reply = Primes.PrimeNumberReply()
    reply.primes = dds.Int32Seq()
    reply.status = Primes.PrimeNumberCalculationStatus.REPLY_IN_PROGRESS

    # prime[i] indicates if i is a prime number
    # Initially, we assume all of them except 0 and 1 are
    prime = [True] * (n + 1)
    prime[0] = False
    prime[1] = False

    m = int(math.sqrt(n))

    for i in range(2, m + 1):
        if prime[i]:
            for j in range(i * i, n + 1, i):
                prime[j] = False

            # Add a new prime number to the reply
            reply.primes.append(i)

            if len(reply.primes) == primes_per_reply:
                # Send a reply now
                replier.send_reply(reply, request_info, final=False)
                reply.primes.clear()

    # Calculation is done. Send remaining prime numbers
    for i in range(m + 1, n + 1):
        if prime[i]:
            reply.primes.append(i)

        if len(reply.primes) == primes_per_reply:
            replier.send_reply(reply, request_info, final=False)
            reply.primes.clear()

    # Send the last reply. Indicate that the calculation is complete and
    # send any prime number left in the sequence
    reply.status = Primes.PrimeNumberCalculationStatus.REPLY_COMPLETED
    replier.send_reply(reply, request_info)


def replier_main(domain_id):
    # Get the QoS from a profile in USER_QOS_PROFILES.xml (the default
    # QosProvider will load the USER_QOS_PROFILES.xml file from the current
    # working directory)
    qos_provider = dds.QosProvider.default

    participant_qos = qos_provider.participant_qos_from_profile(
        "RequestReplyExampleProfiles::ReplierExampleProfile"
    )
    writer_qos = qos_provider.datawriter_qos_from_profile(
        "RequestReplyExampleProfiles::ReplierExampleProfile"
    )
    reader_qos = qos_provider.datareader_qos_from_profile(
        "RequestReplyExampleProfiles::ReplierExampleProfile"
    )




    # Set the logging verbosity to WARNING, INFO, or VERBOSE for more details
    #dds.Logger.instance.verbosity = dds.Verbosity.STATUS_ALL  # Most verbose


    participant = dds.DomainParticipant(domain_id, participant_qos)

    # Create the request topic
    request_topic = dds.Topic(
        participant, 
        "PrimeCalculatorRequest", 
        Primes.PrimeNumberRequest
    )


    filter_expression = "replier_w_guid = %0 OR replier_w_guid = %1"
    filter_parameters = dds.StringSeq(["''", "''"])
    cft_filter = dds.Filter(filter_expression,filter_parameters)

    
    
    content_filtered_topic = dds.ContentFilteredTopic(
        request_topic,
        "FilteredPrimeCalculatorRequest",
        cft_filter
    )

    replier = Replier(
        request_type=Primes.PrimeNumberRequest,
        reply_type=Primes.PrimeNumberReply,
        participant=participant,
        service_name="PrimeCalculator",
        datawriter_qos=writer_qos,
        datareader_qos=reader_qos,
        request_topic=content_filtered_topic,
    )
    replier_r_guid = replier.request_datareader.instance_handle
    replier_w_guid = replier.reply_datawriter.instance_handle
    print(f"Replier request DataReader GUID: {replier_r_guid}")
    print(f"Replier reply DataWriter GUID: {replier_w_guid}")

    print(f"Prime calculation replier started on domain {domain_id}")


    listener = MyDataReaderListener()
    status_mask = (
        dds.StatusMask.SAMPLE_REJECTED |
        dds.StatusMask.SUBSCRIPTION_MATCHED |
        dds.StatusMask.SAMPLE_LOST |
        dds.StatusMask.REQUESTED_DEADLINE_MISSED |
        dds.StatusMask.REQUESTED_INCOMPATIBLE_QOS
    )
    replier.request_datareader.set_listener(listener, status_mask)
    # updating filter parameters
    octet_param = str(replier.reply_datawriter.instance_handle)
    #Now set the filter parameters
    content_filtered_topic.filter_parameters = [
        "''",
        "'{}'".format(octet_param)  
    ]

    max_wait = dds.Duration.from_seconds(200000)
    
    while True:
        try:
            requests: Sequence[
                Tuple[Primes.PrimeNumberRequest, dds.SampleInfo]
            ] = replier.receive_requests(max_wait)
            
            if len(requests) > 0:
                for request, request_info in requests:
                    if not request_info.valid:
                        continue
                    print(f"Received request to calculate prime numbers <= {request.n} in sequences of {request.primes_per_reply}")
                    calculate_and_send_primes(replier, request, request_info)
        except dds.TimeoutError:
            # Timeout occurred, continue waiting for requests
            continue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RTI Connext DDS Example: Request-Reply (Replier)"
    )
    parser.add_argument(
        "-d",
        "--domain",
        type=int,
        default=0,
        help="DDS Domain ID (default: 0)",
    )

    args = parser.parse_args()
    assert 0 <= args.domain < 233

    try:
        replier_main(args.domain)
    except dds.TimeoutError:
        print("Timeout: no requests received")
