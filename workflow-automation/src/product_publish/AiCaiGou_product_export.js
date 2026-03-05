(async () => {
    console.log("🚀 开始全量导出爱采购产品数据...");
    // 1. 配置基础参数
    const baseUrl = "https://b2bwork.baidu.com/api/goods/getList";
    const params = {
        token: "e60044a4b4313261c63f07bcd67d6132",
        froms: "yzs",
        type: "all",
        s: 50, // 每页数量
        isNeedUnit: 1,
        sortby: "addTime",
        order: "desc",
        requestId: "56745826002016311",
        timeStamp: Date.now()
    };

    let allProducts = [];
    let currentPage = 1;
    let totalPages = 1;

    try {
        do {
            // 修正：这里必须使用反引号 `
            console.log(`正在抓取第 ${currentPage} 页...`);

            // 构建带分页的 URL
            const urlParams = new URLSearchParams({ ...params, p: currentPage });
            // 修正：fetch 链接必须使用反引号 `
            const response = await fetch(`${baseUrl}?${urlParams.toString()}`);
            const json = await response.json();

            if (json.status !== 0) {
                // 修正：错误提示也建议使用反引号或正确拼接
                console.error(`第 ${currentPage} 页抓取失败:`, json);
                break;
            }

            const list = json.data.list || [];
            allProducts = allProducts.concat(list);

            // 根据接口返回的 total 计算总页数
            const total = json.data.total;
            totalPages = Math.ceil(total / params.s);
            currentPage++;

            // 稍微停顿一下，避免请求过快
            await new Promise(resolve => setTimeout(resolve, 500));
        } while (currentPage <= totalPages);

        if (allProducts.length === 0) {
            console.warn("未获取到任何产品数据。");
            return;
        }

        // 2. 转换为 CSV
        const headers = ["产品ID", "产品名称", "类目名称", "价格", "单位", "状态", "添加时间", "详情链接"];
        const rows = allProducts.map(item => [
            `'${item.id}`,                                      // 修正：反引号
            `"${item.name.replace(/"/g, '""')}"`,               
            `"${item.category_name}"`,                           
            item.price?.[0]?.price || "0",                       
            `"${item.unit || '台'}"`,                            
            `"${item.status == '60' ? '已发布' : item.status}"`, 
            `"${new Date(item.addTime).toLocaleString()}"`,      
            `"${item.pc_url || ''}"`                             
        ]);

        const csvContent = "\uFEFF" + [headers.join(","), ...rows.map(r => r.join(","))].join("\n");

        // 3. 下载文件
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        // 修正：文件名这里也需要反引号 `
        link.setAttribute("download", `爱采购全量产品列表_${allProducts.length}条.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // 修正：反引号
        console.log(`✅ 完成！共导出 ${allProducts.length} 条数据。`);
    } catch (error) {
        console.error("抓取过程中发生错误:", error);
        alert("导出失败，请检查控制台错误信息。");
    }
})();
