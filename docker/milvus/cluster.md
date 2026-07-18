# Milvus 集群部署说明（P2-D7）

## standalone vs cluster

| 模式 | 适用 | 组件 | 扩展性 |
|---|---|---|---|
| standalone | 开发/小规模 | 单进程（etcd + minio + milvus standalone） | 单机 |
| cluster | 生产/高并发/容灾 | rootcoord + querynode + datanode + indexnode + etcd + minio + pulsar | 水平扩展 |

## 升级路径

当前 `docker/docker-compose.yml` 用 standalone（etcd + minio + milvus standalone）。
100 万级并发（峰值几千 QPS）建议升级 cluster，querynode 可水平扩展承担并发检索。

## cluster 组件职责

- **rootcoord**：集群协调入口，DDL/DML 元数据
- **querycoord + querynode**：查询（querynode 可水平扩展，承担 search，单节点约 1000-2000 QPS）
- **datacoord + datanode**：流式写入（消费 pulsar，写 minio）
- **indexcoord + indexnode**：索引构建（CPU 密集，独立部署避免影响查询）
- **etcd**：元数据存储
- **minio**：对象存储（向量数据，建议 SSD）
- **pulsar**：消息队列（流式处理 WAL）

## 部署

参考官方 cluster docker-compose（v2.4.10）：

```bash
# 下载官方 cluster 配置
curl -L https://github.com/milvus-io/milvus/releases/download/v2.4.10/milvus-cluster-docker-compose.yml \
  -o docker/docker-compose.milvus-cluster.yml

# 启动 cluster
docker compose -f docker/docker-compose.milvus-cluster.yml up -d
```

app 的 `VECTOR_STORE__MILVUS__HOST` 指向 cluster 的 rootcoord 暴露地址（通常 milvus-proxy:19530）。

## 跨实例同步（容灾）

cluster 模式天然多副本：
- querynode 多副本 → 检索高可用（任一节点宕机不影响查询）
- datanode 多副本 → 写入高可用
- minio 跨可用区部署 → 数据高可用

**本地 standalone → 云 cluster 数据迁移**：通过 `scripts/seed_test_data.py --reset` 重新灌入，或直接用 `pymilvus` 脚本导出/导入 collection 数据。

切换后增量向量同步：本地新写入的向量需在云上重新灌入（适合停机窗口；如需增量同步需额外开发 CDC）。

## 性能调优

- **querynode 数量** ≈ 预期并发 QPS / 单节点 QPS（1000-2000）
- **indexnode 独立部署**，避免索引构建抢占查询 CPU
- **minio 用 SSD**，向量检索 IO 密集
- **HNSW 参数**：M=16/efConstruction=200（当前配置），可在 milvus.py 调整
- **ef search**：milvus.py 当前 ef=64，高并发可适当降低换取延迟
