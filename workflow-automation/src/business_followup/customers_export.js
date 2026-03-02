(async function () {
  const PYTHON_SERVER = "http://115.159.145.233:5000/upload";
  const LIST_API = "http://lisungroup.3322.org:6060/bccompany_listOfAjax";
  const ATTACH_API = "http://lisungroup.3322.org:6060/bmail_selectCustomAttachs";
  const MAIL_API = "http://lisungroup.3322.org:6060/bmail_getFollowRecordOfAjax";

  console.log("🚀 全量同步启动（含 email_link）");

  // ----- 兼容非标准JSON -----
  function parseLooseJSON(text) {
    try {
      return JSON.parse(text);
    } catch (e) {
      try {
        return new Function('return ' + text)();
      } catch (e2) {
        console.error("解析失败:", text.slice(0, 100));
        return null;
      }
    }
  }

  // ----- 带超时的fetch -----
  async function fetchWithTimeout(url, options, timeout = 10000) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(id);
      return response;
    } catch (error) {
      clearTimeout(id);
      if (error.name === 'AbortError') throw new Error('请求超时');
      throw error;
    }
  }

  // ----- 带重试的fetch -----
  async function fetchWithRetry(url, options, {
    retries = 3,
    baseDelay = 1000,
    timeout = 10000,
    retryStatuses = [408, 429, 500, 502, 503, 504]
  } = {}) {
    let lastError;
    let lastResponse;
    
    for (let i = 0; i < retries; i++) {
      try {
        const response = await fetchWithTimeout(url, options, timeout);
        if (response.ok) return response;
        lastResponse = response;
        if (retryStatuses.includes(response.status)) {
          console.warn(`⏳ [${url}] 失败 (${response.status})，${i + 1}/${retries} 次重试...`);
          await new Promise(r => setTimeout(r, baseDelay * (i + 1)));
          continue;
        }
        return response;
      } catch (err) {
        lastError = err;
        console.warn(`⏳ [${url}] 网络错误 (${err.message})，${i + 1}/${retries} 次重试...`);
        await new Promise(r => setTimeout(r, baseDelay * (i + 1)));
      }
    }
    if (lastResponse) {
      let body = '';
      try { body = await lastResponse.text(); } catch (e) { body = '无法读取响应体'; }
      throw new Error(`HTTP ${lastResponse.status} - ${body.slice(0, 300)}`);
    }
    throw lastError || new Error(`请求失败，已重试 ${retries} 次`);
  }

  // ===== 最新报价日期 =====
  async function getLatestQuoteDate(comId) {
    try {
      const res = await fetchWithRetry(ATTACH_API, {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
          "x-requested-with": "XMLHttpRequest"
        },
        body: `comId=${comId}&p=1`
      }, { retries: 2, retryStatuses: [408, 429, 500, 502, 503, 504] });

      const text = await res.text();
      const json = parseLooseJSON(text);
      if (!json?.root) return null;

      let latest = null;
      json.root.forEach(row => {
        let name = "", date = "";
        row.forEach(col => {
          if (col.columnName === "attachmentName") name = col.columnValues[0];
          if (col.columnName === "rsDate") date = col.columnValues[0];
        });
        if (name && /QT|Quotation/i.test(name) && date) {
          const currentDate = new Date(date);
          if (!latest || currentDate > new Date(latest)) latest = date;
        }
      });
      return latest;
    } catch (err) {
      console.warn(`获取报价日期失败 ${comId}:`, err.message);
      return null;
    }
  }

  // ===== 邮件统计 =====
  async function getMailStats(comId) {
    let sent = 0, received = 0, page = 1;
    try {
      while (true) {
        const res = await fetchWithRetry(MAIL_API, {
          method: "POST",
          credentials: "include",
          headers: {
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest"
          },
          body: `com_id=${comId}&recordType=mail&p=${page}`
        }, { retries: 2, retryStatuses: [408, 429, 500, 502, 503, 504] });

        const text = await res.text();
        const json = parseLooseJSON(text);
        const list = json?.root || [];
        if (list.length === 0) break;

        list.forEach(m => m.rsflg === "R" ? received++ : sent++);
        if (list.length < 20) break;
        if (page >= 5) { console.warn(`${comId} 邮件过多，只取前5页`); break; }
        page++;
      }
      return {
        sent, received,
        reply_rate: sent > 0 ? +(received / sent * 100).toFixed(2) : 0
      };
    } catch (err) {
      console.warn(`获取邮件统计失败 ${comId}:`, err.message);
      return { sent: 0, received: 0, reply_rate: 0 };
    }
  }

  // ===== 获取客户列表 =====
  async function getAllCustomers() {
    let allCustomers = [], page = 1, total = null;
    const PAGE_SIZE = 100;

    while (true) {
      console.log(`📄 获取第 ${page} 页客户列表...`);
      try {
        const res = await fetchWithRetry(LIST_API, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: `areaId=0&company_tag=myCustomer&p=${page}`
        }, { retries: 3, timeout: 15000, retryStatuses: [408, 429, 500, 502, 503, 504] });

        const text = await res.text();
        const data = parseLooseJSON(text);
        if (!data?.root || data.root.length === 0) break;

        if (data.total && total === null) {
          total = parseInt(data.total);
          console.log(`📊 总记录数: ${total}`);
        }

        const customers = data.root.map(row => {
          let item = {};
          row.forEach(c => item[c.columnHeaderStr || "ID"] = c.columnValues[0] || "");
          return item;
        });

        allCustomers = allCustomers.concat(customers);
        console.log(`✅ 第 ${page} 页: ${customers.length} 条，累计: ${allCustomers.length}`);

        if (total && allCustomers.length >= total) break;
        if (data.root.length < PAGE_SIZE) break;
        if (page >= 100) { console.warn("达到安全上限"); break; }
        page++;
      } catch (err) {
        console.error(`获取第 ${page} 页失败:`, err.message);
        break;
      }
    }

    // 去重
    const unique = [], seen = new Set();
    for (const c of allCustomers) {
      if (!seen.has(c.ID)) { seen.add(c.ID); unique.push(c); }
    }
    console.log(`🎯 共获取 ${unique.length} 个客户（去重前: ${allCustomers.length}）`);
    return unique;
  }

  // ===== 同步单个客户 =====
  async function syncCustomer(item, index, total) {
    const comId = item.ID;
    if (!comId) {
      console.warn(`[${index}/${total}] 跳过无ID客户`);
      return false;
    }

    console.log(`[${index}/${total}] 开始处理: ${comId}`);
    try {
      console.log(`  📎 获取报价...`);
      const quoteDate = await getLatestQuoteDate(comId);
      
      console.log(`  📧 获取邮件...`);
      const mail = await getMailStats(comId);

      // 构造 email_link
      const email_link = `http://lisungroup.3322.org:6060/bmail_getFollowRecord?com_id=${comId}&recordType=customer&isBuyer=0&openWindow=Y`;

      const payload = {
        com_id: comId,
        com_name: item["公司名称"],
        com_area_name: item["区域"],
        s_progress_name: item["销售进度"],
        customer_tag: item["客户状态"],
        last_contact_date: item["最后联系时间"],
        source_name: item["客户来源"],
        rank_name: item["客户等级"],
        business_type_name: item["业务类型"],
        customer_type_name: item["客户类型"],
        oper_date: item["创建日期"],
        contact_email: item["联系人Email"],
        phone: item["联系人电话"],
        latest_quote_date: quoteDate,
        total_emails_sent: mail.sent,
        total_emails_received: mail.received,
        reply_rate: mail.reply_rate,
        email_link: email_link
      };

      console.log(`  💾 上传数据...`);
      
      const postRes = await fetchWithRetry(PYTHON_SERVER, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }, {
        retries: 3,
        timeout: 10000,
        retryStatuses: [404, 408, 429, 500, 502, 503, 504]
      });

      console.log(`✅ [${index}/${total}] ${comId} 同步完成`);
      return true;
    } catch (err) {
      console.error(`❌ [${index}/${total}] ${comId} 同步失败:`, err.message);
      return false;
    }
  }

  // ===== 主流程 =====
  console.log("🚀 开始获取全部客户数据...");
  const customers = await getAllCustomers();
  if (customers.length === 0) { alert("⚠️ 未获取到任何客户数据"); return; }

  console.log(`🔄 开始同步 ${customers.length} 个客户...`);
  let success = 0, failed = 0;

  for (let i = 0; i < customers.length; i++) {
    const ok = await syncCustomer(customers[i], i + 1, customers.length);
    ok ? success++ : failed++;
    
    if ((i + 1) % 10 === 0) {
      console.log(`⏱️ 已处理 ${i + 1} 个，暂停 1 秒...`);
      await new Promise(r => setTimeout(r, 1000));
    }
  }

  console.log(`\n📊 同步完成: 成功 ${success}, 失败 ${failed}, 总计 ${customers.length}`);
  alert(`🎉 同步完成！\n成功: ${success}\n失败: ${failed}\n总计: ${customers.length}`);
})();
