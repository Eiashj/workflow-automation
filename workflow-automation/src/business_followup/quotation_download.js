(async function() {
    try {
        const currentOrigin = window.location.origin; // 自动获取当前域名，如 http://lisungroup.3322.org:6060
        const companyName = prompt("请输入公司全名：", "Accelsius, LLC");
        if (!companyName) return;

        console.log(`🚀 自动适配域名: ${currentOrigin}，正在查询...`);

        // 1. 动态拼接搜索接口
        const searchRes = await fetch(`${currentOrigin}/quotation_listQuo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
            body: `searchValue=${encodeURIComponent(companyName)}&orderByField=quotation_code desc&p=1`
        });

        const responseText = await searchRes.text();
        // 检查登录状态
        if (responseText.includes('<script') || responseText.includes('login')) {
            alert("❌ 登录已失效，请刷新页面重新登录！");
            return;
        }

        const searchData = JSON.parse(responseText);
        const firstRow = searchData.root && searchData.root[0];
        if (!firstRow) throw new Error("未找到对应单据");

        let billId = "", finalCode = "";
        firstRow.forEach(col => {
            const val = (col.columnValues && col.columnValues[0]) ? col.columnValues[0] : "";
            if (col.columnName === "chk") billId = val;
            if (val.includes('QTLS')) {
                const match = val.match(/QTLS\d+/i);
                if (match) finalCode = match[0].toUpperCase();
            }
        });

        // 2. 动态拼接预览和下载链接
        const previewUrl = `${currentOrigin}/poiExcel_previewDefaultPdf?moduleFlg=quotation&billId=${billId}&itemIds=${billId}&tabId=1688`;
        const previewRes = await fetch(previewUrl);
        const html = await previewRes.text();
        const pathMatch = html.match(/\d{6}\/[a-f0-9]{32}\.pdf/);
        const serverPath = pathMatch ? pathMatch[0] : "";

        if (!serverPath) throw new Error("未能抓取到 PDF 路径");

        const downloadUrl = `${currentOrigin}/poiExcel_downLoadExcel?billId=${billId}&name=QUOTATION-${finalCode}.pdf&path=${serverPath}`;
        
        console.log("正在执行二进制重命名下载...");
        const fileRes = await fetch(downloadUrl);
        const blob = await fileRes.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = `${finalCode}-${companyName}.pdf`; 
        document.body.appendChild(link);
        link.click();
        
        window.URL.revokeObjectURL(blobUrl);
        console.log(`🎉 绝杀成功！文件名：${link.download}`);

    } catch (error) {
        console.error('❌ 故障详情:', error);
        alert('出错啦！请确认你是在报价单列表页面运行的脚本。');
    }
})();
