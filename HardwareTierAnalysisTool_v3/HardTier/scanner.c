/*
 * Hardware Tier Analysis Tool - System Scanner v3
 * scanner.c  (systeminfo-backed -- richer data, MinGW-safe)
 *
 * Strategy:
 *   - Parse `systeminfo` output for OS, CPU, RAM, system model, hotfixes, NICs
 *   - Use PowerShell WMI for GPU (systeminfo doesn't expose it)
 *   - Use Windows API GlobalMemoryStatusEx for precise RAM
 *   - Writes results to local_specs.json
 *
 * Compile:
 *   gcc scanner.c -o scanner.exe -O2
 *   (fallback: gcc scanner.c -o scanner.exe -lole32 -loleaut32 -lwbemuuid -lws2_32 -DUNICODE -D_UNICODE -O2)
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

/* ------------------------------------------------------------------ */
/*  Spawn a command, capture its full stdout into buf.                */
/* ------------------------------------------------------------------ */
static int capture_command(const char *cmd, char *buf, size_t buf_size) {
    SECURITY_ATTRIBUTES sa = {0};
    sa.nLength        = sizeof(sa);
    sa.bInheritHandle = TRUE;

    HANDLE hRead, hWrite;
    if (!CreatePipe(&hRead, &hWrite, &sa, 0)) return -1;
    SetHandleInformation(hRead, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOA si = {0};
    si.cb          = sizeof(si);
    si.hStdOutput  = hWrite;
    si.hStdError   = hWrite;
    si.dwFlags     = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;

    PROCESS_INFORMATION pi = {0};
    char cmd_buf[4096];
    strncpy(cmd_buf, cmd, sizeof(cmd_buf)-1);
    cmd_buf[sizeof(cmd_buf)-1] = '\0';

    if (!CreateProcessA(NULL, cmd_buf, NULL, NULL, TRUE,
                        CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        CloseHandle(hWrite); CloseHandle(hRead);
        return -1;
    }
    CloseHandle(hWrite);

    DWORD n;
    size_t total = 0;
    while (total + 1 < buf_size) {
        if (!ReadFile(hRead, buf+total, (DWORD)(buf_size-total-1), &n, NULL) || n==0)
            break;
        total += n;
    }
    buf[total] = '\0';

    WaitForSingleObject(pi.hProcess, 15000);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    CloseHandle(hRead);
    return 0;
}

/* ------------------------------------------------------------------ */
/*  Trim CR/LF/spaces in-place.                                       */
/* ------------------------------------------------------------------ */
static void trim(char *s) {
    size_t start = 0;
    while (s[start]==' '||s[start]=='\t'||s[start]=='\r'||s[start]=='\n') start++;
    if (start) memmove(s, s+start, strlen(s)-start+1);
    size_t l = strlen(s);
    while (l>0 && (s[l-1]==' '||s[l-1]=='\t'||s[l-1]=='\r'||s[l-1]=='\n'))
        s[--l]='\0';
}

/* ------------------------------------------------------------------ */
/*  Extract value from "Key:      Value\r\n" style systeminfo line.  */
/* ------------------------------------------------------------------ */
static int extract_field(const char *haystack, const char *key, char *out, size_t out_size) {
    const char *p = strstr(haystack, key);
    if (!p) return 0;
    p += strlen(key);
    /* skip leading spaces/colons */
    while (*p == ' ' || *p == ':' || *p == '\t') p++;
    /* copy until newline */
    size_t i = 0;
    while (*p && *p != '\r' && *p != '\n' && i + 1 < out_size)
        out[i++] = *p++;
    out[i] = '\0';
    trim(out);
    return i > 0;
}

/* ------------------------------------------------------------------ */
/*  Count lines that start with a given prefix (for hotfixes etc.)   */
/* ------------------------------------------------------------------ */
static int count_bracketed_lines(const char *haystack, const char *section_key) {
    const char *p = strstr(haystack, section_key);
    if (!p) return 0;
    /* skip to end of this line */
    while (*p && *p != '\n') p++;
    int count = 0;
    while (*p) {
        while (*p == '\r' || *p == '\n') p++;
        /* lines like "                           [01]: ..." */
        const char *q = p;
        while (*q == ' ' || *q == '\t') q++;
        if (*q == '[') count++;
        else break;
        while (*p && *p != '\n') p++;
    }
    return count;
}

/* ------------------------------------------------------------------ */
/*  PowerShell query helper.                                           */
/* ------------------------------------------------------------------ */
static void ps_query(const char *expr, char *out, size_t out_size) {
    char cmd[4096];
    snprintf(cmd, sizeof(cmd),
        "powershell.exe -NoProfile -NonInteractive -Command \"%s\"", expr);
    char raw[2048] = {0};
    if (capture_command(cmd, raw, sizeof(raw)) != 0 || raw[0]=='\0') {
        strncpy(out, "Unknown", out_size-1);
        return;
    }
    trim(raw);
    strncpy(out, raw[0] ? raw : "Unknown", out_size-1);
    out[out_size-1] = '\0';
}

/* ------------------------------------------------------------------ */
/*  JSON-escape.                                                       */
/* ------------------------------------------------------------------ */
static void json_escape(const char *src, char *dst, size_t dst_size) {
    size_t j = 0;
    for (size_t i=0; src[i] && j+4<dst_size; i++) {
        unsigned char c = (unsigned char)src[i];
        if      (c=='"')  { dst[j++]='\\'; dst[j++]='"'; }
        else if (c=='\\') { dst[j++]='\\'; dst[j++]='\\'; }
        else if (c=='\n') { dst[j++]='\\'; dst[j++]='n'; }
        else if (c=='\r') { dst[j++]='\\'; dst[j++]='r'; }
        else if (c=='\t') { dst[j++]='\\'; dst[j++]='t'; }
        else              { dst[j++]=(char)c; }
    }
    dst[j]='\0';
}

/* ------------------------------------------------------------------ */
/*  Parse memory string like "15,680 MB" -> integer MB               */
/* ------------------------------------------------------------------ */
static unsigned long long parse_mb(const char *s) {
    char clean[64] = {0};
    size_t j = 0;
    for (size_t i = 0; s[i] && j < sizeof(clean)-1; i++) {
        if (s[i] >= '0' && s[i] <= '9') clean[j++] = s[i];
    }
    clean[j] = '\0';
    return strtoull(clean, NULL, 10);
}

/* ------------------------------------------------------------------ */
/*  main                                                               */
/* ------------------------------------------------------------------ */
int main(void) {
    printf("============================================================\n");
    printf("  Hardware Tier Analysis Tool -- Scanner v3\n");
    printf("  (systeminfo-backed -- richer system data)\n");
    printf("============================================================\n\n");
    fflush(stdout);

    /* ----- 1. Run systeminfo and capture full output ----- */
    printf("[1/6] Running systeminfo (may take 5-15 seconds)...\n"); fflush(stdout);

    /* Use a large buffer -- systeminfo output can be 8-12 KB */
    static char sysinfo[65536];
    memset(sysinfo, 0, sizeof(sysinfo));

    if (capture_command("systeminfo", sysinfo, sizeof(sysinfo)) != 0 || sysinfo[0] == '\0') {
        fprintf(stderr, "[WARNING] systeminfo failed or returned empty. Falling back to PowerShell.\n");
    }

    /* ----- 2. Parse fields from systeminfo ----- */
    char host_name[128]       = "Unknown";
    char os_name[256]         = "Unknown";
    char os_version[128]      = "Unknown";
    char os_build[64]         = "Unknown";
    char sys_manufacturer[128]= "Unknown";
    char sys_model[256]       = "Unknown";
    char sys_type[64]         = "Unknown";
    char cpu_model[512]       = "Unknown";
    char bios_version[128]    = "Unknown";
    char win_dir[128]         = "Unknown";
    char boot_time[64]        = "Unknown";
    char install_date[64]     = "Unknown";
    char time_zone[128]       = "Unknown";
    char total_ram_str[64]    = "Unknown";
    char avail_ram_str[64]    = "Unknown";
    char domain[64]           = "Unknown";
    char logon_server[64]     = "Unknown";

    extract_field(sysinfo, "Host Name:",               host_name,       sizeof(host_name));
    extract_field(sysinfo, "OS Name:",                 os_name,         sizeof(os_name));
    extract_field(sysinfo, "OS Version:",              os_version,      sizeof(os_version));
    extract_field(sysinfo, "System Manufacturer:",     sys_manufacturer,sizeof(sys_manufacturer));
    extract_field(sysinfo, "System Model:",            sys_model,       sizeof(sys_model));
    extract_field(sysinfo, "System Type:",             sys_type,        sizeof(sys_type));
    extract_field(sysinfo, "BIOS Version:",            bios_version,    sizeof(bios_version));
    extract_field(sysinfo, "Windows Directory:",       win_dir,         sizeof(win_dir));
    extract_field(sysinfo, "System Boot Time:",        boot_time,       sizeof(boot_time));
    extract_field(sysinfo, "Original Install Date:",   install_date,    sizeof(install_date));
    extract_field(sysinfo, "Time Zone:",               time_zone,       sizeof(time_zone));
    extract_field(sysinfo, "Total Physical Memory:",   total_ram_str,   sizeof(total_ram_str));
    extract_field(sysinfo, "Available Physical Memory:",avail_ram_str,  sizeof(avail_ram_str));
    extract_field(sysinfo, "Domain:",                  domain,          sizeof(domain));
    extract_field(sysinfo, "Logon Server:",            logon_server,    sizeof(logon_server));

    /* CPU from systeminfo -- line looks like "[01]: AMD64 Family 25 Model 80 Stepping 0 AuthenticAMD ~2301 Mhz" */
    /* We grab the Processor(s) block via PowerShell for cleaner name */
    printf("[2/6] Querying CPU name (PowerShell)...\n"); fflush(stdout);
    ps_query("(Get-WmiObject Win32_Processor | Select-Object -First 1).Name",
             cpu_model, sizeof(cpu_model));

    /* Logical cores */
    printf("[3/6] Querying logical core count...\n"); fflush(stdout);
    char cores_str[32] = "0";
    ps_query("(Get-WmiObject Win32_Processor | "
             "Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum",
             cores_str, sizeof(cores_str));
    int logical_cores = atoi(cores_str);
    if (logical_cores <= 0) logical_cores = 1;

    /* Physical cores */
    char phys_cores_str[32] = "0";
    ps_query("(Get-WmiObject Win32_Processor | "
             "Measure-Object -Property NumberOfCores -Sum).Sum",
             phys_cores_str, sizeof(phys_cores_str));
    int physical_cores = atoi(phys_cores_str);
    if (physical_cores <= 0) physical_cores = 1;

    /* CPU base speed */
    char cpu_speed_str[32] = "0";
    ps_query("(Get-WmiObject Win32_Processor | Select-Object -First 1).MaxClockSpeed",
             cpu_speed_str, sizeof(cpu_speed_str));

    /* ----- 3. RAM via Win32 API (more precise than systeminfo) ----- */
    printf("[4/6] Reading physical RAM...\n"); fflush(stdout);
    MEMORYSTATUSEX mem;
    mem.dwLength = sizeof(MEMORYSTATUSEX);
    GlobalMemoryStatusEx(&mem);
    unsigned long long ram_total_gb =
        (mem.ullTotalPhys + (1ULL<<30) - 1) / (1ULL<<30);
    unsigned long long ram_avail_mb = mem.ullAvailPhys / (1024ULL * 1024ULL);
    unsigned long long ram_total_mb = mem.ullTotalPhys / (1024ULL * 1024ULL);

    /* Parse systeminfo RAM strings as fallback display values */
    unsigned long long si_total_mb = parse_mb(total_ram_str);
    unsigned long long si_avail_mb = parse_mb(avail_ram_str);
    if (si_total_mb == 0) si_total_mb = ram_total_mb;
    if (si_avail_mb == 0) si_avail_mb = ram_avail_mb;

    /* ----- 4. GPU via PowerShell ----- */
    printf("[5/6] Querying GPU...\n"); fflush(stdout);
    char gpu_name[512]   = "Unknown";
    char gpu_driver[128] = "Unknown";
    char gpu_vram[64]    = "Unknown";

    ps_query("(Get-WmiObject Win32_VideoController | Select-Object -First 1).Name",
             gpu_name, sizeof(gpu_name));
    ps_query("(Get-WmiObject Win32_VideoController | Select-Object -First 1).DriverVersion",
             gpu_driver, sizeof(gpu_driver));
    /* VRAM in bytes, convert to MB */
    char vram_bytes[64] = "0";
    ps_query("(Get-WmiObject Win32_VideoController | Select-Object -First 1).AdapterRAM",
             vram_bytes, sizeof(vram_bytes));
    unsigned long long vram_b = strtoull(vram_bytes, NULL, 10);
    if (vram_b > 0) {
        snprintf(gpu_vram, sizeof(gpu_vram), "%llu MB", vram_b / (1024ULL*1024ULL));
    }

    /* All GPUs */
    printf("[6/6] Gathering additional GPU list...\n"); fflush(stdout);
    char all_gpus[2048] = "Unknown";
    ps_query("(Get-WmiObject Win32_VideoController | Select-Object -ExpandProperty Name) -join ' | '",
             all_gpus, sizeof(all_gpus));

    /* ----- Battery (optional -- desktops will return empty) ----- */
    printf("[7/7] Querying battery info...\n"); fflush(stdout);
    char bat_status[64]      = "None";
    char bat_charge_str[32]  = "-1";
    char bat_chemistry[64]   = "Unknown";
    char bat_design_cap[32]  = "0";
    char bat_full_cap[32]    = "0";
    char bat_cycles[32]      = "-1";

    /* EstimatedChargeRemaining: 0-100, or empty if no battery */
    ps_query("$b = Get-WmiObject Win32_Battery | Select-Object -First 1; "
             "if ($b) { $b.EstimatedChargeRemaining } else { '' }",
             bat_charge_str, sizeof(bat_charge_str));

    /* Status string */
    ps_query("$b = Get-WmiObject Win32_Battery | Select-Object -First 1; "
             "if ($b) { switch ($b.BatteryStatus) { "
             "1 {'Discharging'} 2 {'AC - Full'} 3 {'Fully Charged'} "
             "4 {'Low'} 5 {'Critical'} 6 {'Charging'} 7 {'Charging+High'} "
             "8 {'Charging+Low'} 9 {'Charging+Critical'} default {'Unknown'} } } else { 'None' }",
             bat_status, sizeof(bat_status));

    /* Chemistry */
    ps_query("$b = Get-WmiObject Win32_Battery | Select-Object -First 1; "
             "if ($b) { switch ($b.Chemistry) { "
             "1 {'Other'} 2 {'Unknown'} 3 {'Lead Acid'} 4 {'NiCad'} "
             "5 {'NiMH'} 6 {'Li-Ion'} 7 {'Zinc Air'} 8 {'Lithium Polymer'} "
             "default {'Unknown'} } } else { '' }",
             bat_chemistry, sizeof(bat_chemistry));

    /* Design capacity and full-charge capacity via ACPI WMI (mWh) */
    ps_query("try { $s = Get-WmiObject -Namespace root/WMI -Class BatteryStaticData 2>$null | "
             "Select-Object -First 1; if ($s) { $s.DesignedCapacity } else { '0' } } catch { '0' }",
             bat_design_cap, sizeof(bat_design_cap));
    ps_query("try { $f = Get-WmiObject -Namespace root/WMI -Class BatteryFullChargedCapacity 2>$null | "
             "Select-Object -First 1; if ($f) { $f.FullChargedCapacity } else { '0' } } catch { '0' }",
             bat_full_cap, sizeof(bat_full_cap));

    /* Cycle count via BatteryCycleCount (not always available) */
    ps_query("try { $c = Get-WmiObject -Namespace root/WMI -Class BatteryCycleCount 2>$null | "
             "Select-Object -First 1; if ($c) { $c.CycleCount } else { '-1' } } catch { '-1' }",
             bat_cycles, sizeof(bat_cycles));

    int bat_charge  = atoi(bat_charge_str);   /* -1 = no battery */
    int bat_design  = atoi(bat_design_cap);
    int bat_full    = atoi(bat_full_cap);
    int bat_cycle   = atoi(bat_cycles);
    int bat_present = (bat_charge >= 0);

    /* Health % = (full / design) * 100 */
    int bat_health_pct = 0;
    if (bat_present && bat_design > 0 && bat_full > 0)
        bat_health_pct = (int)((double)bat_full / bat_design * 100.0);

    if (bat_present) {
        printf("  Battery      : %d%% charge | %s | health ~%d%%",
               bat_charge, bat_status, bat_health_pct);
        if (bat_cycle >= 0) printf(" | %d cycles", bat_cycle);
        printf("\n");
    } else {
        printf("  Battery      : None (desktop or AC-only)\n");
    }
    fflush(stdout);

    /* Hotfix count */
    int hotfix_count = count_bracketed_lines(sysinfo, "Hotfix(s):");
    int nic_count    = count_bracketed_lines(sysinfo, "Network Card(s):");

    /* ----- Print summary ----- */
    printf("\n------------------------------------------------------------\n");
    printf("  Host         : %s\n", host_name);
    printf("  OS           : %s\n", os_name);
    printf("  Manufacturer : %s\n", sys_manufacturer);
    printf("  Model        : %s\n", sys_model);
    printf("  CPU          : %s\n", cpu_model);
    printf("  Cores        : %d physical / %d logical\n", physical_cores, logical_cores);
    printf("  RAM Total    : %llu MB (%llu GB)\n", si_total_mb, ram_total_gb);
    printf("  RAM Avail    : %llu MB\n", si_avail_mb);
    printf("  GPU          : %s\n", gpu_name);
    if (gpu_vram[0] != '0') printf("  VRAM         : %s\n", gpu_vram);
    printf("  Hotfixes     : %d installed\n", hotfix_count);
    printf("  NICs         : %d installed\n", nic_count);
    printf("  Time Zone    : %s\n", time_zone);
    printf("  Boot Time    : %s\n", boot_time);
    printf("------------------------------------------------------------\n\n");
    fflush(stdout);
    fflush(stdout);

    /* ----- JSON-escape all strings ----- */
    char cpu_esc[1024], gpu_esc[1024], os_esc[512];
    char model_esc[512], mfr_esc[256], bios_esc[256];
    char tz_esc[256], boot_esc[128], domain_esc[128];
    char logon_esc[128], host_esc[256], gpudrv_esc[256];
    char gpuvram_esc[128], all_gpus_esc[2048];
    char sysvr_esc[256], systype_esc[128];
    char bat_status_esc[128], bat_chem_esc[128];

    json_escape(cpu_model,       cpu_esc,      sizeof(cpu_esc));
    json_escape(gpu_name,        gpu_esc,      sizeof(gpu_esc));
    json_escape(os_name,         os_esc,       sizeof(os_esc));
    json_escape(sys_model,       model_esc,    sizeof(model_esc));
    json_escape(sys_manufacturer,mfr_esc,      sizeof(mfr_esc));
    json_escape(bios_version,    bios_esc,     sizeof(bios_esc));
    json_escape(time_zone,       tz_esc,       sizeof(tz_esc));
    json_escape(boot_time,       boot_esc,     sizeof(boot_esc));
    json_escape(domain,          domain_esc,   sizeof(domain_esc));
    json_escape(logon_server,    logon_esc,    sizeof(logon_esc));
    json_escape(host_name,       host_esc,     sizeof(host_esc));
    json_escape(gpu_driver,      gpudrv_esc,   sizeof(gpudrv_esc));
    json_escape(gpu_vram,        gpuvram_esc,  sizeof(gpuvram_esc));
    json_escape(all_gpus,        all_gpus_esc, sizeof(all_gpus_esc));
    json_escape(os_version,      sysvr_esc,    sizeof(sysvr_esc));
    json_escape(sys_type,        systype_esc,  sizeof(systype_esc));
    json_escape(bat_status,      bat_status_esc, sizeof(bat_status_esc));
    json_escape(bat_chemistry,   bat_chem_esc,   sizeof(bat_chem_esc));

    /* CPU speed in MHz */
    int cpu_mhz = atoi(cpu_speed_str);

    /* ----- Write JSON ----- */
    FILE *fp = fopen("local_specs.json", "w");
    if (!fp) {
        fprintf(stderr, "[ERROR] Cannot write local_specs.json\n");
        return 1;
    }

    fprintf(fp,
        "{\n"
        "  \"scanner_version\": \"3.0.0\",\n"
        "  \"system\": {\n"
        "    \"host_name\": \"%s\",\n"
        "    \"manufacturer\": \"%s\",\n"
        "    \"model\": \"%s\",\n"
        "    \"type\": \"%s\",\n"
        "    \"bios_version\": \"%s\",\n"
        "    \"domain\": \"%s\",\n"
        "    \"logon_server\": \"%s\",\n"
        "    \"time_zone\": \"%s\",\n"
        "    \"boot_time\": \"%s\"\n"
        "  },\n"
        "  \"os\": {\n"
        "    \"name\": \"%s\",\n"
        "    \"version\": \"%s\"\n"
        "  },\n"
        "  \"cpu\": {\n"
        "    \"model\": \"%s\",\n"
        "    \"logical_cores\": %d,\n"
        "    \"physical_cores\": %d,\n"
        "    \"base_mhz\": %d\n"
        "  },\n"
        "  \"ram\": {\n"
        "    \"total_gb\": %llu,\n"
        "    \"total_mb\": %llu,\n"
        "    \"available_mb\": %llu\n"
        "  },\n"
        "  \"gpu\": {\n"
        "    \"model\": \"%s\",\n"
        "    \"driver_version\": \"%s\",\n"
        "    \"vram\": \"%s\",\n"
        "    \"all_gpus\": \"%s\"\n"
        "  },\n"
        "  \"hotfixes_installed\": %d,\n"
        "  \"nics_installed\": %d,\n"
        "  \"battery\": {\n"
        "    \"present\": %s,\n"
        "    \"charge_pct\": %d,\n"
        "    \"status\": \"%s\",\n"
        "    \"chemistry\": \"%s\",\n"
        "    \"design_capacity_mwh\": %d,\n"
        "    \"full_capacity_mwh\": %d,\n"
        "    \"health_pct\": %d,\n"
        "    \"cycle_count\": %d\n"
        "  }\n"
        "}\n",
        host_esc, mfr_esc, model_esc, systype_esc, bios_esc,
        domain_esc, logon_esc, tz_esc, boot_esc,
        os_esc, sysvr_esc,
        cpu_esc, logical_cores, physical_cores, cpu_mhz,
        ram_total_gb, si_total_mb, si_avail_mb,
        gpu_esc, gpudrv_esc, gpuvram_esc, all_gpus_esc,
        hotfix_count, nic_count,
        bat_present ? "true" : "false",
        bat_present ? bat_charge : 0,
        bat_status_esc,
        bat_chem_esc,
        bat_design, bat_full,
        bat_health_pct,
        bat_cycle
    );
    fclose(fp);

    printf("[Scanner] local_specs.json written successfully.\n");
    printf("[Scanner] Done.\n\n");
    fflush(stdout);
    return 0;
}
