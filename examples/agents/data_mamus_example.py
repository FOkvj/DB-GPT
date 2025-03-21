import asyncio
import logging
import os
import sys

from typing_extensions import Annotated, Doc

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.react_agent import ReActAgent
from dbgpt.agent.resource import ToolPack, tool
from dbgpt.model.proxy import OpenAILLMClient
from examples.agents.tool import DockerCodeExecuteTool
from examples.agents.tools.docker_code_executor_smart import DockerManager
from jina_web_reader import jina_reader_web_crawler
from dbgpt.agent.expand.resources.search_tool import baidu_search
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


@tool
def terminate(
    final_answer: Annotated[str, Doc("final literal answer about the goal")],
) -> str:
    """When the goal achieved, this tool must be called."""
    return final_answer


@tool
def request_human_help(
        difficulty: Annotated[str, Doc("Description of the difficulty or problem the AI is facing")],
) -> str:
    """当你连续失败3次的时候，可以尝试使用该工具向人类发起求助
    """
    import time
    from threading import Thread, Event

    human_input = [None]
    timeout_event = Event()

    def input_thread():
        print(f"AI needs help: {difficulty}")
        print("Please provide assistance (10 second timeout):")
        human_input[0] = input()
        timeout_event.set()

    thread = Thread(target=input_thread)
    thread.daemon = True
    thread.start()

    # Wait for input or timeout
    timeout_event.wait(timeout=20)

    if human_input[0] is None:
        return "No human input received within timeout period. AI must proceed with best available solution."
    else:
        return f"Human assistance: {human_input[0]}"


@tool
def simple_calculator(first_number: int, second_number: int, operator: str) -> float:
    """Simple calculator tool. Just support +, -, *, /."""
    if isinstance(first_number, str):
        first_number = int(first_number)
    if isinstance(second_number, str):
        second_number = int(second_number)
    if operator == "+":
        return first_number + second_number
    elif operator == "-":
        return first_number - second_number
    elif operator == "*":
        return first_number * second_number
    elif operator == "/":
        return first_number / second_number
    else:
        raise ValueError(f"Invalid operator: {operator}")


@tool
def count_directory_files(path: Annotated[str, Doc("The directory path")]) -> int:
    """Count the number of files in a directory."""
    if not os.path.isdir(path):
        raise ValueError(f"Invalid directory path: {path}")
    return len(os.listdir(path))

async def main():
    llm_client = OpenAILLMClient(
        api_key=os.getenv("API_KEY"),
        model_alias=os.getenv("MODEL"),
        api_base=os.getenv("API_BASE"),
    )
    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="test456")

    context: AgentContext = AgentContext(temperature=1, conv_id="test456", gpts_app_name="ReAct")
    docker_coder_executor = DockerCodeExecuteTool(work_dirs=".", execution_timeout=3000, docker_manager=DockerManager(network_enabled=True, image="ubuntu-data-py311", container_timeout=1800, cleanup_interval=2000))
    tools = ToolPack([simple_calculator, terminate, docker_coder_executor, baidu_search, jina_reader_web_crawler, request_human_help])

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    tool_engineer = (
        await ReActAgent(end_action_name="terminate", max_steps=100)
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(tools)
        .build()
    )

    await user_proxy.initiate_chat(
        recipient=tool_engineer,
        reviewer=user_proxy,
        # message="在当前目录下帮我创建一个的python项目，该项目是一个建议的web服务，访问能直接返回‘hello world！’"
        #         "你帮我写好代码后启动服务，然后测试是否可用，先以后台运行的方式启动服务，然后再写一个客户端去测试，测试成功后保存代码和requirements.txt。（如果缺少依赖请帮我安装）",
        message="收集北京近7天的气温和湿度数据，然后可视化展示出来，将图表保存到当前目录下，不能用假数据，图表中的文字用英文",
        # message="明天几号？北京明天平均气温，最高气温和最低气温分别是多少？给出出处",
    )

    # dbgpt-vis message infos
    print(await agent_memory.gpts_memory.app_link_chat_message("test456"))


if __name__ == "__main__":
    asyncio.run(main())
