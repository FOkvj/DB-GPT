��          �   %   �      p  ^   q  8   �  [   	     e     v  F   �     �     �     �  
   �     �  M     �   V  *   �  ?        E  c   `  s   �  \   8  %   �  5   �  y   �     k     p  ,   �  s   �     +  
  ?  c   J	  -   �	  ]   �	     :
     N
  H   `
     �
     �
     �
     �
     �
  L   �
  q   (  (   �  J   �       T   -  �   �  c        p  9   �  q   �     8     ?  #   U  o   y     �           	                                                         
                                                       Hook init params to pass to the hook constructor(Just for class hook), must be key-value pairs Hook params to pass to the hook, must be key-value pairs Hook path, it can be a class path or a function path. eg: 'dbgpt.config.hooks.env_var_hook' Installed dbgpts Json Serializer Logging level, just support FATAL, ERROR, WARNING, INFO, DEBUG, NOTSET Name Path Repos Repository The class of the tracer storage The current version of the flow, if not set, will read from dbgpt.__version__ The endpoint of the OpenTelemetry Protocol, you can set '${env:OTEL_EXPORTER_OTLP_TRACES_ENDPOINT}' to use the environment variable The exporter of the tracer, e.g. telemetry The file to store the tracer, e.g. dbgpt_webserver_tracer.jsonl The filename to store logs The last version to compatible, if not set, will big than the current version by one minor version. The module to scan, if not set, will scan all DB-GPT modules('dbgpt,dbgpt_client,dbgpt_ext,dbgpt_serve,dbgpt_app'). The output path, if not set, will print to packages/dbgpt-serve/src/dbgpt_serve/flow/compat/ The root operation name of the tracer The serializer for serializing data with json format. The timeout of the connection, in seconds, you can set '${env:OTEL_EXPORTER_OTLP_TRACES_TIMEOUT}' to use the environment  Type Update the template file. Whether the hook is enabled, default is True Whether to use insecure connection, you can set '${env:OTEL_EXPORTER_OTLP_TRACES_INSECURE}' to use the environment  dbgpts In All Repos Project-Id-Version: PACKAGE VERSION
Report-Msgid-Bugs-To: 
PO-Revision-Date: 2025-02-23 13:40+0800
Last-Translator: Automatically generated
Language-Team: none
Language: zh_CN
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit
 传递给钩子构造函数的钩子初始化参数（仅适用于类钩子），必须是键值对 传递给钩子的参数，必须为键值对 钩子路径，可以是类路径或函数路径。例如：'dbgpt.config.hooks.env_var_hook' 已安装的 dbgpts JSON 序列化器 日志级别，仅支持 FATAL、ERROR、WARNING、INFO、DEBUG、NOTSET 名称 路径 仓库 仓库 跟踪器存储的类 当前工作流版本，如果不设置，将从 dbgpt.__version__ 读取。 OpenTelemetry 协议的端点，您可以设置 '${env:OTEL_EXPORTER_OTLP_TRACES_ENDPOINT}' 来使用环境变量 跟踪器的导出器，例如 telemetry 用于存储跟踪器数据的文件，例如 dbgpt_webserver_tracer.jsonl 用于存储日志的文件名 最后兼容的版本，如果不设置，将比当前版本高一个小版本号。 要扫描的模块，如果不设置，将扫描所有 DB-GPT 模块（'dbgpt、dbgpt_client、dbgpt_ext、dbgpt_serve、dbgpt_app'）。 输出路径，如果不设置，将输出到 packages/dbgpt-serve/src/dbgpt_serve/flow/compat/ 。 跟踪器的根操作名称 用于将数据序列化为 JSON 格式的序列化器。 连接的超时时间（秒），您可以设置 '${env:OTEL_EXPORTER_OTLP_TRACES_TIMEOUT}' 来使用环境变量 类型 更新模板文件。 钩子是否启用，默认为 True 是否使用不安全连接，您可以设置 '${env:OTEL_EXPORTER_OTLP_TRACES_INSECURE}' 来使用环境变量 所有仓库中的 dbgpts 