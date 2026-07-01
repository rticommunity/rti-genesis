rti.rpc
rti.rpc is the package containing the RTI Connext Request-Reply and Remote Procedure APIs.

See Request-Reply and Remote Procedure Calls for an overview of the API.

classrti.rpc.Requester(request_type: Union[type, DynamicType], reply_type: Union[type, DynamicType], participant: DomainParticipant, service_name: Optional[str] = None, request_topic: Optional[Union[Topic, Topic, str, object]] = None, reply_topic: Optional[Union[Topic, Topic, str, object]] = None, datawriter_qos: Optional[DataWriterQos] = None, datareader_qos: Optional[DataReaderQos] = None, publisher: Optional[Publisher] = None, subscriber: Optional[Subscriber] = None, on_reply_available: Optional[Callable[[object], object]] = None)
A Requester allows sending requests and receiving replies

Parameters
:
request_type – The type of the request data. It can be an @idl.struct, an @idl.union, or a dds.DynamicType. (See Data Types.)

reply_type – The type of the reply data.

participant – The DomainParticipant that will hold the request writer and reply reader.

service_name – Name that will be used to derive the topic name, defaults to None (rely only on custom topics).

request_topic – Topic object or name that will be used for the request data, must be set if service_name is None, otherwise overrides service_name, defaults to None (use service_name).

reply_topic – Topic object or name that will be used for the reply data, must be set if service_name is None, otherwise overrides service_name, defaults to None (use service_name).

datawriter_qos – QoS object to use for request writer, defaults to None (use default RequestReply QoS).

datareader_qos – QoS object to use for reply reader, defaults to None (use default RequestReply QoS).

publisher – Publisher used to hold request writer, defaults to None (use participant builtin publisher).

subscriber – Subscriber used to hold reply reader, defaults to None (use participant builtin subscriber).

on_reply_available – The callback that handles incoming replies.

__init__(request_type: Union[type, DynamicType], reply_type: Union[type, DynamicType], participant: DomainParticipant, service_name: Optional[str] = None, request_topic: Optional[Union[Topic, Topic, str, object]] = None, reply_topic: Optional[Union[Topic, Topic, str, object]] = None, datawriter_qos: Optional[DataWriterQos] = None, datareader_qos: Optional[DataReaderQos] = None, publisher: Optional[Publisher] = None, subscriber: Optional[Subscriber] = None, on_reply_available: Optional[Callable[[object], object]] = None)→ None
__weakref__
list of weak references to the object (if defined)

close()→ None
Close the resources for this request-reply object.

propertyclosed: bool
Returns true if this request-reply object has been closed.

Getter
:
Returns the number of matched requesters.

classmethodis_final_reply(reply_info: Union[SampleInfo, object])→ bool
Check a reply is the last of the sequence.

Parameters
:
reply_info – The reply info with the flags to check.

Returns
:
Boolean indicating whether reply is the last for a request.

classmethodis_related_reply(request_id: SampleIdentity, reply_info: SampleInfo)→ bool
Check a request if against a reply’s metadata for correlation.

Parameters
:
request_id – The request id used to correlate replies.

reply_info – The reply info used for the correlation check.

Returns
:
Boolean indicating whether the request and reply are correlated.

propertymatched_replier_count: int
The number of discovered matched repliers.

Getter
:
Returns the number of matched repliers.

 
propertyon_reply_available: Optional[Callable[[object], object]]
The listener callback used to process received replies.

Getter
:
Returns the callback function.

Setter
:
Set the callback function.

read_replies(related_request_id: Optional[SampleIdentity] = None)→ Union[LoanedSamples, LoanedSamples]
Read received replies.

Parameters
:
related_request_id – The id used to correlate replies to a specific request, default None (read any replies).

Returns
:
A loaned samples object containing the replies.

receive_replies(max_wait: Duration, min_count: int = 1, related_request_id: Optional[SampleIdentity] = None)→ Union[LoanedSamples, LoanedSamples, object]
Wait for replies and take them.

Parameters
:
max_wait – Maximum time to wait for replies before timing out.

min_count – Minimum number of replies to receive, default 1.

related_request_id – The request id used to correlate replies, default None (receive any replies).

Raises
:
dds.TimeoutError – Thrown if min_count not received within max_wait.

Returns
:
A loaned samples object containing the replies.

propertyreply_datareader: Union[DataReader, DataReader, object]
The DataReader used to receive reply data.

Getter
:
Returns the reply DataReader.

 
propertyrequest_datawriter: Union[DataWriter, DataWriter]
The DataWriter used to send request data.

Getter
:
Returns the request DataWriter.

send_request(request: Union[object, DynamicData], params: Optional[WriteParams] = None)→ SampleIdentity
Send a request and return the identity of the request for correlating received replies.

Parameters
:
request – The request to send.

params – Parameters used for writing the request.

Returns
:
The identity of the request.

take_replies(related_request_id: Optional[SampleIdentity] = None)→ Union[LoanedSamples, LoanedSamples]
Take received replies.

Parameters
:
related_request_id – The id used to correlate replies to a specific request, default None (take any replies).

Returns
:
A loaned samples object containing the replies.

wait_for_replies(max_wait: Duration, min_count: int = 1, related_request_id: Optional[SampleIdentity] = None)→ bool
Wait for received replies.

Parameters
:
max_wait – Maximum time to wait for replies before timing out.

min_count – Minimum number of replies to receive, default 1.

related_request_id – The request id used to correlate replies, default None (receive any replies).

Returns
:
Boolean indicating whether min_count replies were received within max_wait time.

asyncwait_for_replies_async(max_wait: Duration, min_count: int = 1, related_request_id: Optional[SampleIdentity] = None)→ bool
Wait for received replies asynchronously.

Parameters
:
max_wait – Maximum time to wait for replies before timing out.

min_count – Minimum number of replies to receive, default 1.

related_request_id – The request id used to correlate replies, default None (receive any replies).

Returns
:
Boolean indicating whether min_count replies were received within max_wait time.

classrti.rpc.Replier(request_type: Union[type, DynamicType], reply_type: Union[type, DynamicType], participant: DomainParticipant, service_name: Optional[str] = None, request_topic: Optional[Union[Topic, ContentFilteredTopic, str, object]] = None, reply_topic: Optional[Union[Topic, str, object]] = None, datawriter_qos: Optional[DataWriterQos] = None, datareader_qos: Optional[DataReaderQos] = None, publisher: Optional[Publisher] = None, subscriber: Optional[Subscriber] = None, on_request_available: Optional[Callable[[object], object]] = None)
A replier object for handling request-reply interactions with DDS.

Parameters
:
request_type – The type of the request data.

reply_type – The type of the reply data.

participant – The DomainParticipant that will hold the reply writer and request reader.

service_name – Name that will be used to derive the topic name, defaults to None (rely only on custom topics).

request_topic – Topic object or name that will be used for the request data, must be set if service_name is None, otherwise overrides service_name, defaults to None (use service_name).

reply_topic – Topic object or name that will be used for the reply data, must be set if service_name is None, otherwise overrides service_name, defaults to None (use service_name).

datawriter_qos – QoS object to use for reply writer, defaults to None (use default RequestReply QoS).

datareader_qos – QoS object to use for request reader, defaults to None (use default RequestReply QoS).

publisher – Publisher used to hold reply writer, defaults to None (use participant builtin publisher).

subscriber – Subscriber used to hold request reader, defaults to None (use participant builtin subscriber).

on_reply_available – The callback that handles incoming requests.

__init__(request_type: Union[type, DynamicType], reply_type: Union[type, DynamicType], participant: DomainParticipant, service_name: Optional[str] = None, request_topic: Optional[Union[Topic, ContentFilteredTopic, str, object]] = None, reply_topic: Optional[Union[Topic, str, object]] = None, datawriter_qos: Optional[DataWriterQos] = None, datareader_qos: Optional[DataReaderQos] = None, publisher: Optional[Publisher] = None, subscriber: Optional[Subscriber] = None, on_request_available: Optional[Callable[[object], object]] = None)→ None
__weakref__
list of weak references to the object (if defined)

close()→ None
Close the resources for this request-reply object.

propertyclosed: bool
Returns true if this request-reply object has been closed.

Getter
:
Returns the number of matched requesters.

 
propertymatched_requester_count: int
The number of discovered matched requesters.

Getter
:
Returns the number of matched requesters.

 
propertyon_request_available
The listener callback used to process received requests.

Getter
:
Returns the callback function.

Setter
:
Set the callback function.

Type
:
Optional[Callable[[Replier]]]

read_requests()→ Union[LoanedSamples, LoanedSamples]
Read received requests.

Returns
:
A loaned samples object containing the requests.

receive_requests(max_wait: Duration, min_count: int = 1)→ Union[LoanedSamples, LoanedSamples]
Receive a minimum number of requests within a timeout period.

Parameters
:
max_wait – Maximum time to wait for requests before timing out. .

min_count – Minimum number of requests to receive, default 1.

Raises
:
dds.TimeoutError – Thrown if min_count not received within max_wait.

Returns
:
A loaned samples object containing the requests.

propertyreply_datawriter: Union[DataWriter, DataWriter]
The DataWriter used to send reply data.

Getter
:
Returns the reply DataWriter.

 
propertyrequest_datareader: Union[DataReader, DataReader]
The DataReader used to receive request data.

Getter
:
Returns the request DataReader.

send_reply(reply: Union[DynamicData, object], param: Union[SampleIdentity, SampleInfo, WriteParams], final: bool = True)→ None
Send a reply to a received request.

Parameters
:
reply – The reply to send.

param – Parameters used for writing the request.

final – Indicates whether this is the final reply for a specific request, default True.

Raises
:
dds.InvalidArgumentError – Thrown if param is not a type that can be used for correlation.

take_requests()→ Union[LoanedSamples, LoanedSamples]
Take received requests.

Returns
:
A loaned samples object containing the requests.

Return type
:
Union[dds.DynamicData.LoanedSamples, object]

wait_for_requests(max_wait: Duration, min_count: int = 1)→ bool
Wait for a minimum number of requests within a timeout period.

Parameters
:
max_wait – Maximum time to wait for requests before timing out. .

min_count – Minimum number of requests to receive, default 1.

Returns
:
Boolean indicating whether min_count requests were received within max_wait time.

asyncwait_for_requests_async(max_wait: Duration, min_count: Optional[int] = 1)→ bool
Wait asynchronously for a minimum number of requests within a timeout period.

Parameters
:
max_wait – Maximum time to wait for requests before timing out. .

min_count – Minimum number of requests to receive, default 1.

Returns
:
Boolean indicating whether min_count requests were received within max_wait time.

classrti.rpc.SimpleReplier(request_type: Union[DynamicType, type], reply_type: Union[DynamicType, type], participant: DomainParticipant, handler: Callable[[object], object], service_name: Optional[str] = None, request_topic: Optional[Union[Topic, ContentFilteredTopic, str, object]] = None, reply_topic: Optional[Union[Topic, str, object]] = None, datawriter_qos: Optional[DataWriterQos] = None, datareader_qos: Optional[DataReaderQos] = None, publisher: Optional[Publisher] = None, subscriber: Optional[Subscriber] = None)
A special replier that uses a user callback to produce one reply per request.

Parameters
:
request_type – The type of the request data.

reply_type – The type of the reply data.

participant – The DomainParticipant that will hold the request reader and reply writer.

handler – The callback that handles incoming requests and returns a reply. The callback must have a single argument of type request_type and must return an instance of type reply_type.

service_name – Name that will be used to derive the topic name, defaults to None (rely only on custom topics).

request_topic – Topic object or name that will be used for the request data, must be set if service_name is None, otherwise overrides service_name, defaults to None (use service_name).

reply_topic – Topic object or name that will be used for the reply data, must be set if service_name is None, otherwise overrides service_name, defaults to None (use service_name).

datawriter_qos – QoS object to use for reply writer, defaults to None (use default RequestReply QoS).

datareader_qos – QoS object to use for request reader, defaults to None (use default RequestReply QoS).

publisher – Publisher used to hold reply writer, defaults to None (use participant builtin publisher).

subscriber – Subscriber used to hold request reader, defaults to None (use participant builtin subscriber).

__init__(request_type: Union[DynamicType, type], reply_type: Union[DynamicType, type], participant: DomainParticipant, handler: Callable[[object], object], service_name: Optional[str] = None, request_topic: Optional[Union[Topic, ContentFilteredTopic, str, object]] = None, reply_topic: Optional[Union[Topic, str, object]] = None, datawriter_qos: Optional[DataWriterQos] = None, datareader_qos: Optional[DataReaderQos] = None, publisher: Optional[Publisher] = None, subscriber: Optional[Subscriber] = None)→ None
__weakref__
list of weak references to the object (if defined)

close()→ None
Close the resources for this request-reply object.

propertyclosed: bool
Returns true if this request-reply object has been closed.

Getter
:
Returns the number of matched requesters.

 
propertymatched_requester_count: int
The number of discovered matched requesters.

Getter
:
Returns the number of matched requesters.

classrti.rpc.Service(service_instance: ABC, participant: DomainParticipant, service_name: str, task_count: int = 4, datawriter_qos: Optional[DataWriterQos] = None, datareader_qos: Optional[DataReaderQos] = None, publisher: Optional[Publisher] = None, subscriber: Optional[Subscriber] = None)
A service allows running a service_instance in a DDS domain using asyncio.

The service useses a Replier to receive RPC calls and then dispatches them to the service_instance, calling the appropriate method. The value returned by the method is then sent back to the remote caller.

The service runs asynchronously (run method) until the task is cancelled.

close()
Closes the DDS entities used by this service.

propertymatched_client_count: int
The number of RPC clients that match this service.

asyncrun(close_on_cancel: bool = False)
Starts receiving RPC calls (requests) and processing them.

This method runs until the task it returns is cancelled.

If close_on_cancel is True, the service will close the DDS entities when the task is canceled. By default it is False, which means you can call run() again after a run() task is cancelled.

Exceptions raised during the execution of the service are logged as warnings module and do not stop the execution of the service.

classrti.rpc.ClientBase(participant: ~rti.connextdds.DomainParticipant, service_name: str, max_wait_per_call: ~rti.connextdds.Duration = <rti.connextdds.Duration object>, datawriter_qos: ~typing.Optional[~rti.connextdds.DataWriterQos] = None, datareader_qos: ~typing.Optional[~rti.connextdds.DataReaderQos] = None, publisher: ~typing.Optional[~rti.connextdds.Publisher] = None, subscriber: ~typing.Optional[~rti.connextdds.Subscriber] = None)
Base class for RPC clients.

An actual Client must inherit from a service interface and from this class, for example:

` class RobotClient(Robot, rpc.ClientBase): ... `

This base class injects an implementation for all the @operation methods found in Robot, which uses a Requester to make RPC calls and return the values it receives.

The base class also provides an __init__, close and other methods.

close()
Closes the DDS entities used by this client.

propertymatched_service_count: int
The number of RPC services that match this client.

@rti.rpc.service(cls=None, *, type_annotations=[], member_annotations={})
This decorator marks an abstract base class as a remote service interface.

A class annotated with this decorator can be used to create a Client or to define the implementation to be run in a Service.

The operations that will be remotely callable need to be marked with the @operation decorator.

@rti.rpc.operation(funcobj=None, *, raises=[], parameter_annotations={})
This decorator marks a method as an remote operation of a service interface.

It also marks it as an @abc.abstractmethod.

Only methods marked with this decorator will be callable using an RPC Client or an RPC Service.

exceptionrti.rpc.RemoteUnknownOperationError
Exception thrown by a client operation when the server indicates that the operation is unknown to the server.

exceptionrti.rpc.RemoteUnknownExceptionError
Exception thrown by a client operation when the server operation fails with an exception that is not declared in the interface.
---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
