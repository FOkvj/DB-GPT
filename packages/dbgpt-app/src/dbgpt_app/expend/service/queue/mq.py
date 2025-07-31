#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抽象消息队列系统
提供生产者和消费者的接口抽象，方便扩展到不同的消息队列实现
"""

import threading
import json
import time
import uuid
import asyncio
import inspect
import pickle
import base64
import pika
import signal
import sys
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass, asdict, is_dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import logging
from datetime import datetime

from dbgpt import BaseComponent, SystemApp
from dbgpt.component import ComponentType


# 序列化策略枚举
class SerializationStrategy(Enum):
    JSON = "json"
    PICKLE = "pickle"
    AUTO = "auto"


# 消息模式枚举
class MessagePattern(Enum):
    PUBLISH_SUBSCRIBE = "pub_sub"
    POINT_TO_POINT = "p2p"
    REQUEST_RESPONSE = "req_resp"
    BROADCAST = "broadcast"


# 自定义序列化器
class MessageSerializer:
    @staticmethod
    def serialize(data: Any, strategy: SerializationStrategy = SerializationStrategy.AUTO) -> tuple[str, str]:
        """序列化数据，返回: (序列化后的数据, 使用的策略)"""
        if strategy == SerializationStrategy.AUTO:
            strategy = MessageSerializer._detect_strategy(data)

        if strategy == SerializationStrategy.JSON:
            try:
                serialized_data = json.dumps(MessageSerializer._make_json_serializable(data))
                return serialized_data, SerializationStrategy.JSON.value
            except (TypeError, ValueError):
                strategy = SerializationStrategy.PICKLE

        if strategy == SerializationStrategy.PICKLE:
            try:
                pickled_data = pickle.dumps(data)
                encoded_data = base64.b64encode(pickled_data).decode('utf-8')
                return encoded_data, SerializationStrategy.PICKLE.value
            except Exception as e:
                raise ValueError(f"Failed to serialize data: {e}")

    @staticmethod
    def deserialize(data: str, strategy: str) -> Any:
        """反序列化数据"""
        if strategy == SerializationStrategy.JSON.value:
            parsed_data = json.loads(data)
            return MessageSerializer._reconstruct_from_json(parsed_data)
        elif strategy == SerializationStrategy.PICKLE.value:
            try:
                decoded_data = base64.b64decode(data.encode('utf-8'))
                return pickle.loads(decoded_data)
            except Exception as e:
                raise ValueError(f"Failed to deserialize pickle data: {e}")
        else:
            raise ValueError(f"Unknown serialization strategy: {strategy}")

    @staticmethod
    def _detect_strategy(data: Any) -> SerializationStrategy:
        """自动检测最佳序列化策略"""
        if MessageSerializer._is_json_serializable(data):
            return SerializationStrategy.JSON
        else:
            return SerializationStrategy.PICKLE

    @staticmethod
    def _is_json_serializable(data: Any) -> bool:
        """检查数据是否可以JSON序列化"""
        try:
            json.dumps(MessageSerializer._make_json_serializable(data))
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _make_json_serializable(obj: Any) -> Any:
        """尝试将对象转换为JSON可序列化的形式"""
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [MessageSerializer._make_json_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {str(k): MessageSerializer._make_json_serializable(v) for k, v in obj.items()}
        elif is_dataclass(obj):
            return asdict(obj)
        elif MessageSerializer._is_pydantic_model(obj):
            try:
                return {
                    '__pydantic_model__': f"{obj.__class__.__module__}.{obj.__class__.__name__}",
                    'data': obj.model_dump()
                }
            except Exception as e:
                return {
                    '__pydantic_model__': f"{obj.__class__.__module__}.{obj.__class__.__name__}",
                    'data': obj.__dict__,
                    '__serialization_error__': str(e)
                }
        elif hasattr(obj, '__dict__'):
            result = {'__class__': obj.__class__.__name__, '__module__': obj.__class__.__module__}
            result.update(MessageSerializer._make_json_serializable(obj.__dict__))
            return result
        elif isinstance(obj, Enum):
            return {'__enum__': f"{obj.__class__.__module__}.{obj.__class__.__name__}", 'value': obj.value}
        else:
            return str(obj)

    @staticmethod
    def _is_pydantic_model(obj: Any) -> bool:
        """检查对象是否是Pydantic BaseModel (v2)"""
        try:
            return hasattr(obj, 'model_dump') and hasattr(obj, 'model_validate')
        except:
            return False

    @staticmethod
    def _reconstruct_from_json(obj: Any) -> Any:
        """从JSON数据重构对象"""
        if isinstance(obj, dict):
            if '__pydantic_model__' in obj:
                return MessageSerializer._reconstruct_pydantic_model(obj)
            elif '__class__' in obj and '__module__' in obj:
                return MessageSerializer._reconstruct_class_object(obj)
            elif '__enum__' in obj:
                return MessageSerializer._reconstruct_enum(obj)
            else:
                return {k: MessageSerializer._reconstruct_from_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [MessageSerializer._reconstruct_from_json(item) for item in obj]
        else:
            return obj

    @staticmethod
    def _reconstruct_pydantic_model(obj: dict) -> Any:
        """重构Pydantic模型"""
        try:
            module_name, class_name = obj['__pydantic_model__'].rsplit('.', 1)
            module = __import__(module_name, fromlist=[class_name])
            model_class = getattr(module, class_name)
            data = obj['data']
            try:
                return model_class.model_validate(data)
            except Exception as validate_error:
                try:
                    return model_class(**data)
                except Exception:
                    raise validate_error
        except Exception as e:
            print(f"Warning: Failed to reconstruct Pydantic model: {e}")
            return obj.get('data', obj)

    @staticmethod
    def _reconstruct_class_object(obj: dict) -> Any:
        """重构普通类对象"""
        try:
            module_name = obj.pop('__module__')
            class_name = obj.pop('__class__')
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            reconstructed_data = {k: MessageSerializer._reconstruct_from_json(v) for k, v in obj.items()}
            instance = cls.__new__(cls)
            for key, value in reconstructed_data.items():
                setattr(instance, key, value)
            return instance
        except Exception:
            return obj

    @staticmethod
    def _reconstruct_enum(obj: dict) -> Any:
        """重构枚举对象"""
        try:
            module_name, class_name = obj['__enum__'].rsplit('.', 1)
            module = __import__(module_name, fromlist=[class_name])
            enum_class = getattr(module, class_name)
            return enum_class(obj['value'])
        except Exception:
            return obj['value']


# 消息数据结构
@dataclass
class Message:
    id: str
    pattern: MessagePattern
    topic: str
    data: Any
    timestamp: float
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None
    headers: Dict[str, Any] = None
    _serialization_strategy: Optional[str] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}

    def serialize_data(self, strategy: SerializationStrategy = SerializationStrategy.AUTO) -> 'Message':
        """序列化消息数据，返回新的Message对象"""
        serialized_data, used_strategy = MessageSerializer.serialize(self.data, strategy)

        new_message = Message(
            id=self.id,
            pattern=self.pattern,
            topic=self.topic,
            data=serialized_data,
            timestamp=self.timestamp,
            reply_to=self.reply_to,
            correlation_id=self.correlation_id,
            headers=self.headers.copy(),
            _serialization_strategy=used_strategy
        )
        return new_message

    def deserialize_data(self) -> 'Message':
        """反序列化消息数据，返回新的Message对象"""
        if self._serialization_strategy:
            deserialized_data = MessageSerializer.deserialize(self.data, self._serialization_strategy)

            new_message = Message(
                id=self.id,
                pattern=self.pattern,
                topic=self.topic,
                data=deserialized_data,
                timestamp=self.timestamp,
                reply_to=self.reply_to,
                correlation_id=self.correlation_id,
                headers=self.headers.copy()
            )
            return new_message
        return self

    def to_dict(self) -> dict:
        """转换为字典格式用于传输"""
        return {
            'id': self.id,
            'pattern': self.pattern.value,
            'topic': self.topic,
            'data': self.data,
            'timestamp': self.timestamp,
            'reply_to': self.reply_to,
            'correlation_id': self.correlation_id,
            'headers': self.headers,
            '_serialization_strategy': self._serialization_strategy
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Message':
        """从字典创建Message对象"""
        return cls(
            id=data['id'],
            pattern=MessagePattern(data['pattern']),
            topic=data['topic'],
            data=data['data'],
            timestamp=data['timestamp'],
            reply_to=data.get('reply_to'),
            correlation_id=data.get('correlation_id'),
            headers=data.get('headers', {}),
            _serialization_strategy=data.get('_serialization_strategy')
        )


# ============================
# 抽象接口定义
# ============================

class MessageProducerInterface(ABC):
    """消息生产者抽象接口"""

    @abstractmethod
    def connect(self) -> bool:
        """建立连接"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def publish_message(self, message: Message):
        """发布消息"""
        pass

    @abstractmethod
    def send_request(self, message: Message, timeout: float = 30.0) -> Optional[Message]:
        """发送请求并等待响应"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass


class MessageConsumerInterface(ABC):
    """消息消费者抽象接口"""

    @abstractmethod
    def connect(self) -> bool:
        """建立连接"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def subscribe_point_to_point(self, topic: str, callback: Union[Callable[[Any], None], Callable[[Any], Callable]]):
        """订阅点对点模式消息"""
        pass

    @abstractmethod
    def subscribe_publish_subscribe(self, topic: str,
                                    callback: Union[Callable[[Any], None], Callable[[Any], Callable]]):
        """订阅发布订阅模式消息"""
        pass

    @abstractmethod
    def start_consuming(self):
        """开始消费消息"""
        pass

    @abstractmethod
    def stop_consuming(self):
        """停止消费消息"""
        pass

    @abstractmethod
    def is_consuming(self) -> bool:
        """检查是否正在消费"""
        pass


class MessageQueueManagerInterface(ABC):
    """消息队列管理器抽象接口"""

    @abstractmethod
    def get_producer(self) -> MessageProducerInterface:
        """获取生产者实例"""
        pass

    @abstractmethod
    def create_consumer(self, consumer_id: str = None) -> MessageConsumerInterface:
        """创建消费者实例"""
        pass

    @abstractmethod
    def publish_point_to_point(self, topic: str, data: Any, **kwargs):
        """发布点对点消息"""
        pass

    @abstractmethod
    def publish_broadcast(self, topic: str, data: Any, **kwargs):
        """发布广播/发布订阅消息"""
        pass

    @abstractmethod
    def subscribe_point_to_point(self, topic: str, callback: Union[Callable[[Any], None], Callable[[Any], Callable]],
                                 consumer_id: str = None) -> MessageConsumerInterface:
        """订阅点对点消息"""
        pass

    @abstractmethod
    def subscribe_broadcast(self, topic: str, callback: Union[Callable[[Any], None], Callable[[Any], Callable]],
                            consumer_id: str = None) -> MessageConsumerInterface:
        """订阅广播/发布订阅消息"""
        pass

    @abstractmethod
    def shutdown(self):
        """关闭所有连接"""
        pass


# ============================
# RabbitMQ具体实现
# ============================

import time
import logging
from typing import Union, Optional


class RabbitMQProducer(MessageProducerInterface):
    """RabbitMQ消息生产者实现"""

    def __init__(self, host='localhost', port=5672, virtual_host='/', username='guest', password='guest'):
        self.connection_params = pika.ConnectionParameters(
            host=host,
            port=port,
            virtual_host=virtual_host,
            credentials=pika.PlainCredentials(username, password),
            heartbeat=600,
            blocked_connection_timeout=300
        )
        self.connection = None
        self.channel = None
        self.logger = logging.getLogger(f"{__name__}.RabbitMQProducer")
        self._lock = threading.RLock()

    def connect(self) -> bool:
        """建立连接"""
        try:
            with self._lock:
                if self.is_connected():
                    return True

                self.connection = pika.BlockingConnection(self.connection_params)
                self.channel = self.connection.channel()
                self.logger.info("RabbitMQ Producer connected")
                return True
        except Exception as e:
            self.logger.error(f"Failed to connect producer: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        try:
            with self._lock:
                if self.channel and not self.channel.is_closed:
                    self.channel.close()
                if self.connection and not self.connection.is_closed:
                    self.connection.close()
                self.logger.info("RabbitMQ Producer disconnected")
        except Exception as e:
            self.logger.error(f"Error disconnecting producer: {e}")

    def is_connected(self) -> bool:
        """检查连接状态"""
        return (self.connection and not self.connection.is_closed and
                self.channel and not self.channel.is_closed)

    def publish_message(self, message: Message, max_retries: int = 3, retry_delay: float = 1.0):
        """发布消息（带重试机制）

        Args:
            message: 要发布的消息
            max_retries: 最大重试次数，默认3次
            retry_delay: 重试延迟时间（秒），默认1.0秒
        """
        last_exception = None

        for attempt in range(max_retries + 1):  # +1 因为第一次不算重试
            try:
                with self._lock:
                    # 检查并重新连接
                    if not self.is_connected():
                        self.logger.info(f"Connection lost, reconnecting (attempt {attempt + 1}/{max_retries + 1})")
                        if not self.connect():
                            raise RuntimeError("Failed to connect to RabbitMQ")

                    # 序列化消息
                    serialized_message = message.serialize_data()
                    message_body = json.dumps(serialized_message.to_dict(), ensure_ascii=False)

                    if message.pattern == MessagePattern.PUBLISH_SUBSCRIBE:
                        # 发布订阅模式：使用交换机
                        self.channel.exchange_declare(
                            exchange=message.topic,
                            exchange_type='fanout',
                            durable=True
                        )
                        self.channel.basic_publish(
                            exchange=message.topic,
                            routing_key='',
                            body=message_body,
                            properties=pika.BasicProperties(
                                delivery_mode=2,  # 持久化
                                correlation_id=message.correlation_id,
                                timestamp=int(message.timestamp)
                            )
                        )
                        self.logger.info(f"Published message to exchange: {message.topic}")
                    else:
                        # 点对点模式：使用队列
                        self.channel.queue_declare(queue=message.topic, durable=True)
                        self.channel.basic_publish(
                            exchange='',
                            routing_key=message.topic,
                            body=message_body,
                            properties=pika.BasicProperties(
                                delivery_mode=2,  # 持久化
                                reply_to=message.reply_to,
                                correlation_id=message.correlation_id,
                                timestamp=int(message.timestamp)
                            )
                        )
                        self.logger.info(f"Published message to queue: {message.topic}")

                # 如果执行到这里，说明发送成功
                if attempt > 0:
                    self.logger.info(f"Message published successfully after {attempt} retries")
                return

            except Exception as e:
                last_exception = e
                self.logger.warning(f"Failed to publish message (attempt {attempt + 1}/{max_retries + 1}): {e}")

                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries:
                    # 连接失败时断开连接以便下次重新连接
                    try:
                        self.disconnect()
                    except:
                        pass

                    self.logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)

                    # 指数退避：每次重试时间加倍
                    retry_delay *= 2
                else:
                    # 最后一次重试失败
                    self.logger.error(f"Failed to publish message after {max_retries + 1} attempts")
                    raise last_exception

    def send_request(self, message: Message, timeout: float = 30.0, max_retries: int = 3) -> Optional[Message]:
        """发送请求并等待响应（带重试机制）

        Args:
            message: 要发送的消息
            timeout: 响应超时时间
            max_retries: 最大重试次数，默认3次
        """
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                with self._lock:
                    if not self.is_connected():
                        if not self.connect():
                            raise RuntimeError("Failed to connect to RabbitMQ")

                    # 创建临时回复队列
                    reply_queue = self.channel.queue_declare(queue='', exclusive=True)
                    reply_queue_name = reply_queue.method.queue

                    message.reply_to = reply_queue_name
                    message.correlation_id = str(uuid.uuid4())

                    # 发送请求（不使用重试，因为这里已经在重试循环中）
                    self._publish_message_internal(message)

                    # 等待响应
                    response = None
                    start_time = time.time()

                    def on_response(ch, method, props, body):
                        nonlocal response
                        if props.correlation_id == message.correlation_id:
                            message_data = json.loads(body.decode('utf-8'))
                            response = Message.from_dict(message_data).deserialize_data()
                            ch.basic_ack(delivery_tag=method.delivery_tag)

                    self.channel.basic_consume(
                        queue=reply_queue_name,
                        on_message_callback=on_response
                    )

                    while response is None and (time.time() - start_time) < timeout:
                        self.connection.process_data_events(time_limit=1)

                    return response

            except Exception as e:
                last_exception = e
                self.logger.warning(f"Failed to send request (attempt {attempt + 1}/{max_retries + 1}): {e}")

                if attempt < max_retries:
                    try:
                        self.disconnect()
                    except:
                        pass
                    time.sleep(1.0 * (2 ** attempt))  # 指数退避
                else:
                    self.logger.error(f"Failed to send request after {max_retries + 1} attempts")
                    raise last_exception

        return None

    def _publish_message_internal(self, message: Message):
        """内部发布消息方法（不带重试）"""
        # 序列化消息
        serialized_message = message.serialize_data()
        message_body = json.dumps(serialized_message.to_dict(), ensure_ascii=False)

        if message.pattern == MessagePattern.PUBLISH_SUBSCRIBE:
            # 发布订阅模式：使用交换机
            self.channel.exchange_declare(
                exchange=message.topic,
                exchange_type='fanout',
                durable=True
            )
            self.channel.basic_publish(
                exchange=message.topic,
                routing_key='',
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # 持久化
                    correlation_id=message.correlation_id,
                    timestamp=int(message.timestamp)
                )
            )
        else:
            # 点对点模式：使用队列
            self.channel.queue_declare(queue=message.topic, durable=True)
            self.channel.basic_publish(
                exchange='',
                routing_key=message.topic,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # 持久化
                    reply_to=message.reply_to,
                    correlation_id=message.correlation_id,
                    timestamp=int(message.timestamp)
                )
            )

class RabbitMQConsumer(MessageConsumerInterface):
    """RabbitMQ消息消费者实现"""

    def __init__(self, host='localhost', port=5672, virtual_host='/', username='guest', password='guest'):
        self.connection_params = pika.ConnectionParameters(
            host=host,
            port=port,
            virtual_host=virtual_host,
            credentials=pika.PlainCredentials(username, password),
            heartbeat=600,
            blocked_connection_timeout=300
        )
        self.connection = None
        self.channel = None
        self.consuming = False
        self.consumer_thread = None
        self.logger = logging.getLogger(f"{__name__}.RabbitMQConsumer")
        self.callback_executor = ThreadPoolExecutor(max_workers=10)
        self.event_loop = None
        self.loop_thread = None
        self._message_callback = None
        self._topic = None
        self._pattern = None

    def connect(self) -> bool:
        """建立连接"""
        try:
            self.connection = pika.BlockingConnection(self.connection_params)
            self.channel = self.connection.channel()
            self.logger.info("RabbitMQ Consumer connected")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect consumer: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        self.stop_consuming()

        if self.event_loop:
            self.event_loop.call_soon_threadsafe(self.event_loop.stop)
        if self.loop_thread:
            self.loop_thread.join(timeout=2)
        self.callback_executor.shutdown(wait=True)

        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            self.logger.info("RabbitMQ Consumer disconnected")
        except Exception as e:
            self.logger.error(f"Error disconnecting consumer: {e}")

    def is_consuming(self) -> bool:
        """检查是否正在消费"""
        return self.consuming

    def _start_event_loop(self):
        """启动事件循环用于异步回调"""

        def run_event_loop():
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            self.event_loop.run_forever()

        self.loop_thread = threading.Thread(target=run_event_loop)
        self.loop_thread.daemon = True
        self.loop_thread.start()

        # 等待事件循环启动
        while self.event_loop is None:
            time.sleep(0.01)

    def _execute_callback(self, callback: Union[Callable[[Any], None], Callable[[Any], Callable]], data: Any):
        """执行回调函数，支持同步和异步"""
        try:
            if inspect.iscoroutinefunction(callback):
                # 异步回调
                if self.event_loop and not self.event_loop.is_closed():
                    asyncio.run_coroutine_threadsafe(callback(data), self.event_loop)
                else:
                    self.logger.warning("Event loop not available for async callback")
            else:
                # 同步回调，在线程池中执行
                self.callback_executor.submit(callback, data)
        except Exception as e:
            self.logger.error(f"Error executing callback: {e}")

    def _on_message(self, channel, method, properties, body):
        """内部消息处理回调"""
        try:
            # 解析消息
            message_data = json.loads(body.decode('utf-8'))
            message = Message.from_dict(message_data).deserialize_data()

            self.logger.info(f"Received message: {message.id} from {method.routing_key}")

            # 执行用户回调
            if self._message_callback:
                self._execute_callback(self._message_callback, message.data)

            # 确认消息
            channel.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def subscribe_point_to_point(self, topic: str, callback: Union[Callable[[Any], None], Callable[[Any], Callable]]):
        """订阅点对点模式消息"""
        self._topic = topic
        self._pattern = MessagePattern.POINT_TO_POINT
        self._message_callback = callback

        if not self.connect():
            raise RuntimeError("Failed to connect to RabbitMQ")

        # 启动事件循环
        self._start_event_loop()

        # RabbitMQ实现：声明队列
        self.channel.queue_declare(queue=topic, durable=True)
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=topic,
            on_message_callback=self._on_message
        )

        self.logger.info(f"Subscribed to point-to-point topic: {topic}")

    def subscribe_publish_subscribe(self, topic: str,
                                    callback: Union[Callable[[Any], None], Callable[[Any], Callable]]):
        """订阅发布订阅模式消息"""
        self._topic = topic
        self._pattern = MessagePattern.PUBLISH_SUBSCRIBE
        self._message_callback = callback

        if not self.connect():
            raise RuntimeError("Failed to connect to RabbitMQ")

        # 启动事件循环
        self._start_event_loop()

        # RabbitMQ实现：声明交换机
        self.channel.exchange_declare(exchange=topic, exchange_type='fanout', durable=True)

        # 创建临时队列并绑定到交换机
        result = self.channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        self.channel.queue_bind(exchange=topic, queue=queue_name)

        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=self._on_message
        )

        self.logger.info(f"Subscribed to publish-subscribe topic: {topic}, queue: {queue_name}")

    def start_consuming(self):
        """开始消费消息"""
        if self.consuming:
            return

        self.consuming = True

        def consume_loop():
            try:
                self.logger.info("Starting message consumption")
                while self.consuming:
                    try:
                        self.connection.process_data_events(time_limit=1)
                    except Exception as e:
                        if self.consuming:
                            self.logger.error(f"Error in consumption loop: {e}")
                        break
            except Exception as e:
                self.logger.error(f"Consumer loop failed: {e}")
            finally:
                self.logger.info("Consumer loop ended")

        self.consumer_thread = threading.Thread(target=consume_loop, name=f"Consumer-{self._topic}")
        self.consumer_thread.daemon = True
        self.consumer_thread.start()

        self.logger.info("Consumer thread started")

    def stop_consuming(self):
        """停止消费消息"""
        if not self.consuming:
            return

        self.consuming = False

        try:
            if self.channel and not self.channel.is_closed:
                self.channel.stop_consuming()
        except Exception as e:
            self.logger.error(f"Error stopping consumption: {e}")

        if self.consumer_thread and self.consumer_thread.is_alive():
            self.consumer_thread.join(timeout=5)

        self.logger.info("Consumer stopped")


class RabbitMQManager(MessageQueueManagerInterface, BaseComponent):
    """RabbitMQ消息队列管理器实现"""
    name = ComponentType.MESSAGE_QUEUE_MANAGER

    def __init__(self, host='localhost', port=5672, virtual_host='/', username='guest', password='guest', **kwargs):
        super().__init__(**kwargs)
        self.connection_params = {
            'host': host,
            'port': port,
            'virtual_host': virtual_host,
            'username': username,
            'password': password
        }
        self.producer = None
        self.consumers = {}
        self.logger = logging.getLogger(f"{__name__}.RabbitMQManager")

    def init_app(self, system_app: SystemApp):
        pass
    def get_producer(self) -> MessageProducerInterface:
        """获取生产者实例（单例）"""
        if not self.producer:
            self.producer = RabbitMQProducer(**self.connection_params)
        return self.producer

    def create_consumer(self, consumer_id: str = None) -> MessageConsumerInterface:
        """创建新的消费者实例"""
        if not consumer_id:
            consumer_id = f"consumer_{uuid.uuid4().hex[:8]}"

        consumer = RabbitMQConsumer(**self.connection_params)
        self.consumers[consumer_id] = consumer
        return consumer

    def publish_point_to_point(self, topic: str, data: Any, **kwargs):
        """发布点对点消息"""
        message = Message(
            id=str(uuid.uuid4()),
            pattern=MessagePattern.POINT_TO_POINT,
            topic=topic,
            data=data,
            timestamp=time.time(),
            **kwargs
        )
        producer = self.get_producer()
        producer.publish_message(message)

    def publish_broadcast(self, topic: str, data: Any, **kwargs):
        """发布广播/发布订阅消息"""
        message = Message(
            id=str(uuid.uuid4()),
            pattern=MessagePattern.PUBLISH_SUBSCRIBE,
            topic=topic,
            data=data,
            timestamp=time.time(),
            **kwargs
        )
        producer = self.get_producer()
        producer.publish_message(message)

    def subscribe_point_to_point(self, topic: str, callback: Union[Callable[[Any], None], Callable[[Any], Callable]],
                                 consumer_id: str = None) -> MessageConsumerInterface:
        """订阅点对点消息并开始消费"""
        consumer = self.create_consumer(consumer_id)
        consumer.subscribe_point_to_point(topic, callback)
        consumer.start_consuming()
        return consumer

    def subscribe_broadcast(self, topic: str, callback: Union[Callable[[Any], None], Callable[[Any], Callable]],
                            consumer_id: str = None) -> MessageConsumerInterface:
        """订阅广播/发布订阅消息并开始消费"""
        consumer = self.create_consumer(consumer_id)
        consumer.subscribe_publish_subscribe(topic, callback)
        consumer.start_consuming()
        return consumer

    def shutdown(self):
        """关闭所有连接"""
        # 停止所有消费者
        for consumer_id, consumer in self.consumers.items():
            self.logger.info(f"Stopping consumer: {consumer_id}")
            consumer.disconnect()

        # 关闭生产者
        if self.producer:
            self.producer.disconnect()

        self.logger.info("RabbitMQ Manager shutdown complete")


# ============================
# 工厂模式支持多种消息队列
# ============================

class MessageQueueFactory:
    """消息队列工厂，支持创建不同类型的消息队列管理器"""

    @staticmethod
    def create_manager(queue_type: str = "rabbitmq", **connection_params) -> MessageQueueManagerInterface:
        """创建消息队列管理器

        Args:
            queue_type: 队列类型 ("rabbitmq", "kafka", "redis" 等)
            **connection_params: 连接参数

        Returns:
            消息队列管理器实例
        """
        if queue_type.lower() == "rabbitmq":
            return RabbitMQManager(**connection_params)
        elif queue_type.lower() == "kafka":
            # 未来可以添加 Kafka 实现
            raise NotImplementedError("Kafka implementation not yet available")
        elif queue_type.lower() == "redis":
            # 未来可以添加 Redis 实现
            raise NotImplementedError("Redis implementation not yet available")
        else:
            raise ValueError(f"Unsupported queue type: {queue_type}")


# ============================
# 便捷的装饰器支持
# ============================

def message_handler(queue_manager: MessageQueueManagerInterface, topic: str, mode: str = "point_to_point"):
    """消息处理装饰器

    Args:
        queue_manager: 消息队列管理器
        topic: 主题名称
        mode: 模式 ("point_to_point" 或 "broadcast")
    """

    def decorator(func):
        if mode == "point_to_point":
            queue_manager.subscribe_point_to_point(topic, func)
        elif mode == "broadcast":
            queue_manager.subscribe_broadcast(topic, func)
        else:
            raise ValueError(f"Unsupported mode: {mode}")
        return func

    return decorator