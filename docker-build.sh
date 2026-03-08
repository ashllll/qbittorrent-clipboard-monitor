#!/bin/bash
# qBittorrent Clipboard Monitor - Docker 多架构构建脚本
# 支持 amd64, arm64, arm/v7 架构

set -e

# 配置
IMAGE_NAME="qbittorrent-clipboard-monitor"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
ALPINE_VERSION="${ALPINE_VERSION:-3.19}"
APP_VERSION="${APP_VERSION:-3.0.0}"
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印信息函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助
show_help() {
    cat << EOF
qBittorrent Clipboard Monitor Docker 构建脚本

用法: $0 [选项] [命令]

命令:
    build       构建镜像（默认）
    push        构建并推送多架构镜像到仓库
    test        测试本地镜像
    clean       清理构建缓存

选项:
    -t, --tag TAG       镜像标签 (默认: latest)
    -p, --platforms     目标平台，逗号分隔 (默认: linux/amd64,linux/arm64)
    -r, --registry      镜像仓库前缀 (如: docker.io/username)
    -h, --help          显示此帮助

环境变量:
    PYTHON_VERSION      Python 版本 (默认: 3.11)
    ALPINE_VERSION      Alpine 版本 (默认: 3.19)
    APP_VERSION         应用版本 (默认: 3.0.0)

示例:
    # 本地构建
    $0 build

    # 构建特定标签
    $0 build -t v3.0.0

    # 多架构构建并推送
    $0 push -t v3.0.0 -r docker.io/username

    # 仅构建 ARM64
    $0 build -p linux/arm64 -t arm64-latest
EOF
}

# 解析参数
TAG="latest"
PLATFORMS="linux/amd64,linux/arm64"
REGISTRY=""
COMMAND="build"

while [[ $# -gt 0 ]]; do
    case $1 in
        build|push|test|clean)
            COMMAND="$1"
            shift
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -p|--platforms)
            PLATFORMS="$2"
            shift 2
            ;;
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 构建完整镜像名
if [[ -n "$REGISTRY" ]]; then
    FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"
else
    FULL_IMAGE_NAME="${IMAGE_NAME}:${TAG}"
fi

# 检查 Docker 是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    log_info "Docker 版本: $(docker --version)"
}

# 检查 buildx
check_buildx() {
    if ! docker buildx version &> /dev/null; then
        log_error "Docker buildx 未安装或不可用"
        exit 1
    fi
    log_info "Buildx 版本: $(docker buildx version | head -1)"
}

# 创建 buildx 构建器
create_builder() {
    local builder_name="qb-monitor-builder"
    
    if docker buildx inspect "$builder_name" &> /dev/null; then
        log_info "使用已存在的构建器: $builder_name"
    else
        log_info "创建新的 buildx 构建器: $builder_name"
        docker buildx create --name "$builder_name" --driver docker-container --use
    fi
    
    # 启动构建器并检查支持的 platforms
    docker buildx inspect --bootstrap > /dev/null 2>&1
}

# 构建镜像
do_build() {
    log_info "开始构建镜像..."
    log_info "  镜像名: ${FULL_IMAGE_NAME}"
    log_info "  平台: ${PLATFORMS}"
    log_info "  Python: ${PYTHON_VERSION}"
    log_info "  Alpine: ${ALPINE_VERSION}"
    log_info "  版本: ${APP_VERSION}"
    
    # 本地构建（单平台）
    if [[ "$PLATFORMS" == "local" ]] || [[ "$PLATFORMS" == *","* ]]; then
        # 多平台或本地模式，使用 buildx
        docker buildx build \
            --platform "$PLATFORMS" \
            --tag "$FULL_IMAGE_NAME" \
            --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
            --build-arg ALPINE_VERSION="$ALPINE_VERSION" \
            --build-arg APP_VERSION="$APP_VERSION" \
            --build-arg BUILD_DATE="$BUILD_DATE" \
            --build-arg VCS_REF="$VCS_REF" \
            --target production \
            --load \
            .
    else
        # 传统构建（单平台）
        docker build \
            --tag "$FULL_IMAGE_NAME" \
            --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
            --build-arg ALPINE_VERSION="$ALPINE_VERSION" \
            --build-arg APP_VERSION="$APP_VERSION" \
            --build-arg BUILD_DATE="$BUILD_DATE" \
            --build-arg VCS_REF="$VCS_REF" \
            --target production \
            .
    fi
    
    log_success "镜像构建完成: ${FULL_IMAGE_NAME}"
}

# 构建并推送多架构镜像
do_push() {
    if [[ -z "$REGISTRY" ]]; then
        log_error "推送镜像需要指定仓库地址，使用 -r 参数"
        exit 1
    fi
    
    log_info "开始构建并推送多架构镜像..."
    log_info "  目标仓库: ${REGISTRY}"
    log_info "  平台: ${PLATFORMS}"
    
    create_builder
    
    docker buildx build \
        --platform "$PLATFORMS" \
        --tag "$FULL_IMAGE_NAME" \
        --tag "${REGISTRY}/${IMAGE_NAME}:latest" \
        --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
        --build-arg ALPINE_VERSION="$ALPINE_VERSION" \
        --build-arg APP_VERSION="$APP_VERSION" \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VCS_REF="$VCS_REF" \
        --target production \
        --push \
        --progress plain \
        .
    
    log_success "镜像推送完成!"
    log_info "  镜像地址: ${FULL_IMAGE_NAME}"
    
    # 显示镜像信息
    docker buildx imagetools inspect "$FULL_IMAGE_NAME" || true
}

# 测试镜像
do_test() {
    log_info "测试本地镜像..."
    
    if ! docker image inspect "$FULL_IMAGE_NAME" &> /dev/null; then
        log_error "镜像不存在: ${FULL_IMAGE_NAME}"
        log_info "请先运行: $0 build"
        exit 1
    fi
    
    # 检查镜像大小
    local size=$(docker images --format "{{.Size}}" "$FULL_IMAGE_NAME")
    log_info "镜像大小: $size"
    
    # 检查镜像层
    log_info "镜像层信息:"
    docker history "$FULL_IMAGE_NAME" --format "table{{.Size}}\t{{.CreatedBy}}" | head -20
    
    # 测试运行
    log_info "测试容器运行..."
    docker run --rm "$FULL_IMAGE_NAME" --version || true
    
    log_success "测试完成!"
}

# 清理缓存
do_clean() {
    log_info "清理构建缓存..."
    docker builder prune -f
    docker buildx prune -f 2>/dev/null || true
    log_success "清理完成!"
}

# 主函数
main() {
    log_info "qBittorrent Clipboard Monitor Docker 构建脚本"
    log_info "命令: $COMMAND"
    
    check_docker
    
    case "$COMMAND" in
        build)
            check_buildx
            do_build
            ;;
        push)
            check_buildx
            do_push
            ;;
        test)
            do_test
            ;;
        clean)
            do_clean
            ;;
        *)
            log_error "未知命令: $COMMAND"
            show_help
            exit 1
            ;;
    esac
}

main
