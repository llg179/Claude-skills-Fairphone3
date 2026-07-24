// SPDX-License-Identifier: GPL-2.0-only
/*
 * framer_mmio_dump.c - snapshot the SLIMbus/LPASS framer + clock MMIO blocks so
 * they can be retrieved after an ADSP subsystem-restart (SSR).
 *
 * Why: the WCD9335 SLIMbus framer control/status registers live at AP-physical
 * 0x0c140000 (LPASS_AP alias of the ADSP-view 0xee140000). The framer's clock
 * controller (audio_core_slimbus_core_clk, RCGR/CBCR) lives at the LPASS_AP
 * clock-controller alias 0x0c000000 (framer branch CBCR at +0x12014). Both
 * blocks are AP-readable live while the ADSP is up and the block is clocked.
 * During an ADSP SSR teardown the clock can get gated, after which a naive MMIO
 * read HANGS. This module captures each region with memcpy_fromio() at
 * SUBSYS_BEFORE_SHUTDOWN (clock guaranteed still on) into kernel buffers exposed
 * through debugfs, so they survive the SSR and can be pulled with a plain `cat`.
 *
 * A manual "trigger" exercises the same capture path live for validation.
 *
 * Breadcrumb: grep dmesg for "FRAMERDUMP:".
 */

#include <linux/debugfs.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/notifier.h>
#include <linux/slab.h>
#include <linux/vmalloc.h>
#include <linux/ktime.h>
#include <soc/qcom/subsystem_notif.h>

struct fd_region {
	const char		*name;
	unsigned long		phys;
	unsigned long		size;
	void			*buf;
	struct debugfs_blob_wrapper blob;
};

static struct fd_region fd_regions[] = {
	/* LPASS clock controller: framer RCGR/CBCR at +0x12000/+0x12014 (C1 lead). */
	{ .name = "lpasscc", .phys = 0x0c000000UL, .size = 0x14000UL },
	/* SLIMbus/LPASS framer window (NGD-mapped 0x0c140000..0x0c16bfff, 176 KiB). */
	{ .name = "framer",  .phys = 0x0c140000UL, .size = 0x2c000UL },
};
#define FD_NREG ARRAY_SIZE(fd_regions)

static struct dentry *fd_dir;
static void *fd_subsys_handle;

static bool fd_captured;
static u64 fd_capture_ns;
static const char *fd_capture_src = "none";
/* Key registers cached at capture time for quick eyeballing. */
static u32 fd_fr004, fd_fr010, fd_fr400, fd_fr404, fd_fr600, fd_fr604, fd_fr610;
static u32 fd_ck004, fd_ck014;	/* framer clock RCGR CFG (+0x12004) + CBCR (+0x12014) */

static void fd_capture_one(struct fd_region *r)
{
	void __iomem *io = ioremap(r->phys, r->size);

	if (!io) {
		pr_err("FRAMERDUMP: ioremap(%s 0x%08lx,0x%lx) failed\n",
		       r->name, r->phys, r->size);
		return;
	}
	memcpy_fromio(r->buf, io, r->size);
	iounmap(io);
}

static void framer_capture(const char *src)
{
	size_t i;
	u8 *fr = NULL, *ck = NULL;

	for (i = 0; i < FD_NREG; i++) {
		fd_capture_one(&fd_regions[i]);
		if (!strcmp(fd_regions[i].name, "framer"))
			fr = fd_regions[i].buf;
		else if (!strcmp(fd_regions[i].name, "lpasscc"))
			ck = fd_regions[i].buf;
	}

	if (fr) {
		fd_fr004 = *(u32 *)(fr + 0x004);
		fd_fr010 = *(u32 *)(fr + 0x010);
		fd_fr400 = *(u32 *)(fr + 0x400);
		fd_fr404 = *(u32 *)(fr + 0x404);
		fd_fr600 = *(u32 *)(fr + 0x600);
		fd_fr604 = *(u32 *)(fr + 0x604);
		fd_fr610 = *(u32 *)(fr + 0x610);
	}
	if (ck) {
		fd_ck004 = *(u32 *)(ck + 0x12004);	/* RCGR CFG */
		fd_ck014 = *(u32 *)(ck + 0x12014);	/* framer branch CBCR */
	}

	fd_captured = true;
	fd_capture_ns = ktime_get_ns();
	fd_capture_src = src;

	pr_info("FRAMERDUMP: captured (src=%s) framer[+004=%08x +404=%08x(FRM_STAT) +604=%08x] clk[CFG=%08x CBCR=%08x]\n",
		src, fd_fr004, fd_fr404, fd_fr604, fd_ck004, fd_ck014);
}

static int framer_adsp_notifier(struct notifier_block *nb,
				unsigned long action, void *data)
{
	if (action == SUBSYS_BEFORE_SHUTDOWN) {
		pr_info("FRAMERDUMP: adsp SUBSYS_BEFORE_SHUTDOWN, capturing\n");
		framer_capture("adsp-before-shutdown");
	}
	return NOTIFY_DONE;
}

static struct notifier_block framer_nb = {
	.notifier_call = framer_adsp_notifier,
};

static ssize_t fd_trigger_write(struct file *f, const char __user *ubuf,
				size_t len, loff_t *off)
{
	pr_info("FRAMERDUMP: manual trigger via debugfs\n");
	framer_capture("manual-trigger");
	return len;
}

static const struct file_operations fd_trigger_fops = {
	.owner = THIS_MODULE,
	.write = fd_trigger_write,
	.open = simple_open,
	.llseek = default_llseek,
};

static int fd_info_show(struct seq_file *s, void *unused)
{
	size_t i;

	seq_printf(s, "captured:  %d\nsource:    %s\nwhen_ns:   %llu\n",
		   fd_captured, fd_capture_src, fd_capture_ns);
	for (i = 0; i < FD_NREG; i++)
		seq_printf(s, "region %-8s phys=0x%08lx size=0x%lx\n",
			   fd_regions[i].name, fd_regions[i].phys,
			   fd_regions[i].size);
	if (fd_captured) {
		seq_printf(s, "framer +0x004=0x%08x +0x010=0x%08x +0x400=0x%08x(FRM_CFG) +0x404=0x%08x(FRM_STAT)\n",
			   fd_fr004, fd_fr010, fd_fr400, fd_fr404);
		seq_printf(s, "framer +0x600=0x%08x +0x604=0x%08x +0x610=0x%08x\n",
			   fd_fr600, fd_fr604, fd_fr610);
		seq_printf(s, "clk    RCGR_CFG(+0x12004)=0x%08x  framer_CBCR(+0x12014)=0x%08x\n",
			   fd_ck004, fd_ck014);
	}
	return 0;
}

static int fd_info_open(struct inode *inode, struct file *file)
{
	return single_open(file, fd_info_show, NULL);
}

static const struct file_operations fd_info_fops = {
	.owner = THIS_MODULE,
	.open = fd_info_open,
	.read = seq_read,
	.llseek = seq_lseek,
	.release = single_release,
};

static int __init framer_mmio_dump_init(void)
{
	size_t i;

	for (i = 0; i < FD_NREG; i++) {
		fd_regions[i].buf = vzalloc(fd_regions[i].size);
		if (!fd_regions[i].buf) {
			while (i--)
				vfree(fd_regions[i].buf);
			return -ENOMEM;
		}
		fd_regions[i].blob.data = fd_regions[i].buf;
		fd_regions[i].blob.size = fd_regions[i].size;
	}

	fd_dir = debugfs_create_dir("framerdump", NULL);
	if (!IS_ERR_OR_NULL(fd_dir)) {
		for (i = 0; i < FD_NREG; i++)
			debugfs_create_blob(fd_regions[i].name, 0400, fd_dir,
					    &fd_regions[i].blob);
		debugfs_create_file("trigger", 0200, fd_dir, NULL,
				    &fd_trigger_fops);
		debugfs_create_file("info", 0400, fd_dir, NULL, &fd_info_fops);
	} else {
		pr_warn("FRAMERDUMP: debugfs unavailable, buffers still capture\n");
	}

	fd_subsys_handle = subsys_notif_register_notifier("adsp", &framer_nb);
	if (IS_ERR_OR_NULL(fd_subsys_handle))
		pr_warn("FRAMERDUMP: could not register adsp subsys notifier (%ld)\n",
			PTR_ERR(fd_subsys_handle));

	pr_info("FRAMERDUMP: init ok, %zu regions (lpasscc 0x14000 + framer 0x2c000)\n",
		FD_NREG);
	return 0;
}

static void __exit framer_mmio_dump_exit(void)
{
	size_t i;

	if (!IS_ERR_OR_NULL(fd_subsys_handle))
		subsys_notif_unregister_notifier(fd_subsys_handle, &framer_nb);
	debugfs_remove_recursive(fd_dir);
	for (i = 0; i < FD_NREG; i++)
		vfree(fd_regions[i].buf);
}

module_init(framer_mmio_dump_init);
module_exit(framer_mmio_dump_exit);
MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("SLIMbus/LPASS framer + clock MMIO snapshot for post-SSR retrieval");
