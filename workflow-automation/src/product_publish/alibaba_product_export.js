// ===================== Allie 的阿里巴巴產品導出工具 (完整修復版) =====================
const API_URL = "https://hz-productposting.alibaba.com/product/managementproducts/asyQueryProductsList.do";
const REQUEST_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
};

const PAGE_SIZE = 50;
const REQUEST_DELAY = 2000;

// 固定參數 (請確保 ctoken 和 tb_token 與妳瀏覽器當前的一致)
const FIXED_REQUEST_PARAMS = {
    "statisticsType": "month",
    "repositoryType": "all",
    "imageType": "all",
    "showPowerScore": "",
    "showType": "onlyMarket",
    "status": "all",
    "size": "50",
    "ctoken": "29c0_erq454h",
    "tb_token": "e3b9be5e17943",
    "csrf_token": "4eda921b-dbc3-4ec6-99d5-e5dbc8f97182",
    "lang": "en_US"
};

class ProductFetcher {
    constructor() {
        this.allProducts = [];
        this.totalPages = 0;
        this.totalCount = 0;
    }

    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        console.log(`[${timestamp}] [${type.toUpperCase()}] ${message}`);
    }

    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    buildRequestUrl(page) {
        const params = new URLSearchParams();
        Object.entries(FIXED_REQUEST_PARAMS).forEach(([key, value]) => {
            if (value) params.append(key, value);
        });
        params.set("page", page);
        return `${API_URL}?${params.toString()}`;
    }

    async fetchPage(page) {
        const url = this.buildRequestUrl(page);
        try {
            const response = await fetch(url, { method: 'GET', credentials: 'include' });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (!data.result) throw new Error('API 返回錯誤');
            return data;
        } catch (error) {
            this.log(`第 ${page} 頁獲取失敗: ${error.message}`, 'error');
            return null;
        }
    }

    extractData(data) {
        if (!data?.products) return [];
        return data.products
            .filter(p => p.status === "approved" && (p.isDisplay === "Y" || p.displayStatus === "y"))
            .map(p => ({
                "產品型號": p.redModel || "無型號",
                "產品詳情頁鏈接": p.detailUrl || "無鏈接",
                "產品ID": p.id || "無ID",
                "最後修改時間": p.gmtModified || "無修改時間"
            }));
    }

    async start() {
        this.log('🚀 開始執行任務...', 'info');
        
        // 1. 獲取第一頁
        const firstPageData = await this.fetchPage(1);
        if (!firstPageData) return;

        this.totalCount = firstPageData.count || 0;
        this.totalPages = Math.ceil(this.totalCount / PAGE_SIZE);
        this.allProducts.push(...this.extractData(firstPageData));
        this.log(`發現總產品數: ${this.totalCount}, 預計總頁數: ${this.totalPages}`, 'info');

        // 2. 循環獲取後續頁面
        for (let page = 2; page <= this.totalPages; page++) {
            this.log(`正在抓取第 ${page}/${this.totalPages} 頁...`);
            await this.delay(REQUEST_DELAY);
            const data = await this.fetchPage(page);
            if (data) {
                this.allProducts.push(...this.extractData(data));
            }
        }

        // 3. 導出 CSV
        this.exportToCSV();
    }

    exportToCSV() {
        if (this.allProducts.length === 0) {
            this.log("沒有符合條件的數據可以導出", "warning");
            return;
        }

        const headers = ["產品型號", "產品詳情頁鏈接", "產品ID", "最後修改時間"];
        let csvContent = "\uFEFF" + headers.join(",") + "\n";
        
        this.allProducts.forEach(item => {
            const row = headers.map(header => `"${(item[header] || "").toString().replace(/"/g, '""')}"`);
            csvContent += row.join(",") + "\n";
        });

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `Alibaba_Export_${new Date().getTime()}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        this.log(`✅ 導出成功！共計 ${this.allProducts.length} 條數據。`, 'success');
    }
}

// 啟動
const myFetcher = new ProductFetcher();
myFetcher.start();
