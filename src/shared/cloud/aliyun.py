"""阿里云容灾 API 对接模块（P0-DR-Aliyun）

支持阿里云的以下容灾能力：
    1. 云解析 DNS（PrivateZone / 公网 DNS）— 通过修改解析记录切换流量
    2. OSS 对象存储 — 备份文件上传
    3. 云监控（CMS）— 自定义指标上报
    4. 飞书/钉钉 webhook — 告警通知

依赖：
    pip install alibabacloud_alidns20150109 oss2

环境变量：
    ALIYUN_ACCESS_KEY_ID     — 阿里云 AccessKey ID
    ALIYUN_ACCESS_KEY_SECRET — 阿里云 AccessKey Secret
    ALIYUN_REGION            — 地域（默认 cn-hangzhou）
    ALIYUN_OSS_BUCKET        — OSS bucket 名（备份用）
    ALIYUN_OSS_ENDPOINT      — OSS endpoint
    ALIYUN_DNS_DOMAIN        — DNS 域名（流量切换用，可选）
    ALIYUN_DNS_RECORD_ID     — DNS 解析记录 ID（流量切换用，可选）

注意：
    1. AccessKey 建议使用 RAM 子账号，仅授予必要权限（DNS/OSS 读写）
    2. 不要将 AccessKey 提交到代码中，使用环境变量
    3. 阿里云轻量服务器不自带 SLB，流量切换通过 DNS 或 Nginx 实现
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("aliyun_dr")

# 从环境变量读取凭证
_ACCESS_KEY_ID = os.getenv("ALIYUN_ACCESS_KEY_ID", "")
_ACCESS_KEY_SECRET = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")
_REGION = os.getenv("ALIYUN_REGION", "cn-hangzhou")
_OSS_BUCKET = os.getenv("ALIYUN_OSS_BUCKET", "")
_OSS_ENDPOINT = os.getenv("ALIYUN_OSS_ENDPOINT", f"https://oss-{_REGION}.aliyuncs.com")
_DNS_DOMAIN = os.getenv("ALIYUN_DNS_DOMAIN", "")
_DNS_RECORD_ID = os.getenv("ALIYUN_DNS_RECORD_ID", "")


def _check_credentials() -> bool:
    """检查阿里云凭证是否配置。"""
    if not _ACCESS_KEY_ID or not _ACCESS_KEY_SECRET:
        logger.warning("阿里云凭证未配置（ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET）")
        return False
    return True


# ─── DNS 流量切换 ───


def switch_dns_to_backup(backup_ip: str, ttl: int = 60) -> bool:
    """将 DNS 解析切换到备机 IP。

    通过阿里云云解析 DNS API 修改 A 记录，将域名指向备机 IP。
    切换后全球 DNS 缓存在 TTL（默认 60s）后生效。

    前置条件：
        - 配置了 ALIYUN_DNS_DOMAIN 和 ALIYUN_DNS_RECORD_ID
        - RAM 账号有 alidns:UpdateDomainRecord 权限

    Args:
        backup_ip: 备机公网 IP
        ttl: DNS TTL（秒），切换时建议调低到 60s

    Returns:
        是否成功
    """
    if not _check_credentials():
        return False

    if not _DNS_DOMAIN or not _DNS_RECORD_ID:
        logger.warning("DNS 域名/记录 ID 未配置，跳过 DNS 切换")
        return False

    try:
        from alibabacloud_alidns20150109 import models
        from alibabacloud_alidns20150109.client import Client
        from alibabacloud_tea_openapi.models import Config

        config = Config(
            access_key_id=_ACCESS_KEY_ID,
            access_key_secret=_ACCESS_KEY_SECRET,
            endpoint=f"alidns.{_REGION}.aliyuncs.com",
        )
        client = Client(config)

        # 更新解析记录
        request = models.UpdateDomainRecordRequest(
            record_id=_DNS_RECORD_ID,
            rr=_DNS_DOMAIN.split(".")[0],  # 主机记录
            type="A",
            value=backup_ip,
            ttl=ttl,
        )

        response = client.update_domain_record(request)
        logger.info(f"[DNS] 解析已切换到 {backup_ip} (TTL={ttl}s, request_id={response.body.request_id})")
        return True

    except ImportError:
        logger.warning("[DNS] alibabacloud_alidns 未安装，跳过 DNS 切换")
        logger.warning("      安装: pip install alibabacloud_alidns20150109")
        return False
    except Exception as e:
        logger.error(f"[DNS] 切换失败: {e}")
        return False


def switch_dns_to_primary(primary_ip: str, ttl: int = 600) -> bool:
    """将 DNS 解析切回主节点 IP。

    Args:
        primary_ip: 主节点公网 IP
        ttl: DNS TTL（秒），正常时用较长 TTL 减少查询
    """
    return switch_dns_to_backup(primary_ip, ttl)


# ─── OSS 备份上传 ───


def upload_to_oss(local_path: str, oss_key: str | None = None) -> str | None:
    """将本地文件上传到阿里云 OSS。

    用于备份文件异地存储，提高数据安全性。

    Args:
        local_path: 本地文件路径
        oss_key: OSS 对象 key（不指定则用文件名）

    Returns:
        OSS URL，失败返回 None
    """
    if not _check_credentials():
        return None

    if not _OSS_BUCKET:
        logger.warning("OSS bucket 未配置（ALIYUN_OSS_BUCKET），跳过上传")
        return None

    try:
        import oss2

        auth = oss2.Auth(_ACCESS_KEY_ID, _ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, _OSS_ENDPOINT, _OSS_BUCKET)

        if oss_key is None:
            import os

            oss_key = f"edu_rag/backups/{os.path.basename(local_path)}"

        # 断点续传上传（适合大文件）
        oss2.resumable_upload(
            bucket,
            oss_key,
            local_path,
            store=oss2.ResumableStore(root="/tmp"),
            multipart_threshold=10 * 1024 * 1024,  # 10MB 以上分片
            part_size=5 * 1024 * 1024,
        )  # 5MB 分片

        url = f"https://{_OSS_BUCKET}.{_OSS_ENDPOINT.replace('https://', '')}/{oss_key}"
        logger.info(f"[OSS] 上传成功: {url}")
        return url

    except ImportError:
        logger.warning("[OSS] oss2 未安装，跳过上传")
        logger.warning("      安装: pip install oss2")
        return None
    except Exception as e:
        logger.error(f"[OSS] 上传失败: {e}")
        return None


def download_from_oss(oss_key: str, local_path: str) -> bool:
    """从 OSS 下载文件。"""
    if not _check_credentials() or not _OSS_BUCKET:
        return False

    try:
        import oss2

        auth = oss2.Auth(_ACCESS_KEY_ID, _ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, _OSS_ENDPOINT, _OSS_BUCKET)

        oss2.resumable_download(
            bucket,
            oss_key,
            local_path,
            store=oss2.ResumableStore(root="/tmp"),
            multipart_threshold=10 * 1024 * 1024,
            part_size=5 * 1024 * 1024,
        )
        logger.info(f"[OSS] 下载成功: {oss_key} → {local_path}")
        return True

    except ImportError:
        logger.warning("[OSS] oss2 未安装")
        return False
    except Exception as e:
        logger.error(f"[OSS] 下载失败: {e}")
        return False


# ─── 云监控自定义指标 ───


def report_metric(metric_name: str, value: float, dimensions: dict | None = None) -> bool:
    """上报自定义监控指标到阿里云云监控（CMS）。

    用于将 failover 事件、复制延迟等指标上报到云监控，
    配合告警规则实现自动告警。

    Args:
        metric_name: 指标名（如 edu_rag_failover_triggered）
        value: 指标值
        dimensions: 维度（如 {"instance": "primary"}）
    """
    if not _check_credentials():
        return False

    try:
        from alibabacloud_cms20190101 import models
        from alibabacloud_cms20190101.client import Client
        from alibabacloud_tea_openapi.models import Config

        config = Config(
            access_key_id=_ACCESS_KEY_ID,
            access_key_secret=_ACCESS_KEY_SECRET,
            endpoint=f"metrics.{_REGION}.aliyuncs.com",
        )
        client = Client(config)

        dims = [
            models.PutCustomMetricItem(
                metric_name=metric_name,
                value=str(value),
                dimensions=json.dumps(dimensions or {}),
                period="60",
            )
        ]

        request = models.PutCustomMetricRequest(metric_list=dims)
        client.put_custom_metric(request)
        logger.info(f"[CMS] 指标上报: {metric_name}={value}")
        return True

    except ImportError:
        logger.debug("[CMS] alibabacloud_cms 未安装，跳过指标上报")
        return False
    except Exception as e:
        logger.error(f"[CMS] 指标上报失败: {e}")
        return False


# ─── 飞书/钉钉/企业微信 webhook ───


def send_feishu_alert(webhook_url: str, title: str, content: str) -> bool:
    """发送飞书 webhook 告警。

    Args:
        webhook_url: 飞书机器人 webhook URL
        title: 告警标题
        content: 告警内容
    """
    try:
        import httpx

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🔔 {title}"},
                    "template": "red" if "告警" in title or "FAILOVER" in title else "green",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": content},
                    }
                ],
            },
        }

        r = httpx.post(webhook_url, json=payload, timeout=10)
        if r.status_code == 200 and r.json().get("code", 0) == 0:
            logger.info("[飞书] 告警发送成功")
            return True
        else:
            logger.error(f"[飞书] 告警发送失败: {r.text}")
            return False

    except Exception as e:
        logger.error(f"[飞书] 告警异常: {e}")
        return False


def send_dingtalk_alert(webhook_url: str, title: str, content: str, at_all: bool = False) -> bool:
    """发送钉钉 webhook 告警。

    Args:
        webhook_url: 钉钉机器人 webhook URL
        title: 告警标题
        content: 告警内容
        at_all: 是否 @所有人
    """
    try:
        import httpx

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {title}\n\n{content}",
            },
            "at": {
                "isAtAll": at_all,
            },
        }

        r = httpx.post(webhook_url, json=payload, timeout=10)
        if r.status_code == 200 and r.json().get("errcode", 0) == 0:
            logger.info("[钉钉] 告警发送成功")
            return True
        else:
            logger.error(f"[钉钉] 告警发送失败: {r.text}")
            return False

    except Exception as e:
        logger.error(f"[钉钉] 告警异常: {e}")
        return False


def send_wechat_alert(webhook_url: str, content: str) -> bool:
    """发送企业微信 webhook 告警。"""
    try:
        import httpx

        payload = {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }

        r = httpx.post(webhook_url, json=payload, timeout=10)
        if r.status_code == 200 and r.json().get("errcode", 0) == 0:
            logger.info("[企业微信] 告警发送成功")
            return True
        else:
            logger.error(f"[企业微信] 告警发送失败: {r.text}")
            return False

    except Exception as e:
        logger.error(f"[企业微信] 告警异常: {e}")
        return False


# ─── 阿里云轻量服务器快照备份 ───


def create_lighthouse_snapshot(instance_id: str, snapshot_name: str) -> str | None:
    """创建阿里云轻量服务器磁盘快照。

    快照是轻量服务器最简单的备份方式，可用于整机恢复。

    前置条件：
        - RAM 账号有 lighthouse:CreateSnapshot 权限
        - 已配置 ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET

    Args:
        instance_id: 轻量服务器实例 ID
        snapshot_name: 快照名称

    Returns:
        快照 ID，失败返回 None
    """
    if not _check_credentials():
        return None

    try:
        from alibabacloud_lighthouse20201230 import models
        from alibabacloud_lighthouse20201230.client import Client
        from alibabacloud_tea_openapi.models import Config

        config = Config(
            access_key_id=_ACCESS_KEY_ID,
            access_key_secret=_ACCESS_KEY_SECRET,
            endpoint="lighthouse.cn-hangzhou.aliyuncs.com",
        )
        client = Client(config)

        request = models.CreateSnapshotRequest(
            instance_id=instance_id,
            snapshot_name=snapshot_name,
        )
        response = client.create_snapshot(request)
        snapshot_id = response.body.snapshot_id
        logger.info(f"[快照] 创建成功: {snapshot_name} (id={snapshot_id})")
        return snapshot_id

    except ImportError:
        logger.warning("[快照] alibabacloud_lighthouse 未安装")
        logger.warning("      安装: pip install alibabacloud_lighthouse20201230")
        return None
    except Exception as e:
        logger.error(f"[快照] 创建失败: {e}")
        return None
