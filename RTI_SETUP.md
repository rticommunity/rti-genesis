# RTI Connext DDS Setup Guide

This guide walks you through getting RTI Connext DDS, which GENESIS needs to run.

**Time required:** 10-15 minutes

---

## Quick Start (Recommended)

Just run the setup wizard:

```bash
./rti_setup.sh
```

The wizard will guide you through everything. Follow the prompts and you'll be done in minutes.

---

## What You'll Do

| Step | What Happens | Time |
|------|--------------|------|
| 1 | Fill out a short form on RTI's website | 2 min |
| 2 | Download the software | 2-5 min |
| 3 | Install it (like any other app) | 3-5 min |
| 4 | Get your license from email | 1 min |
| 5 | The wizard configures everything | 1 min |

---

## Detailed Steps

### Step 1: Run the Wizard

Open your terminal and run:

```bash
./rti_setup.sh
```

You'll see:

```
╔═══════════════════════════════════════════════════════════════╗
║          RTI Connext DDS Setup Wizard for GENESIS             ║
╚═══════════════════════════════════════════════════════════════╝

  Welcome! This wizard will help you set up RTI Connext DDS.
  It takes about 10-15 minutes to complete.

  You will need:
    • A web browser
    • An email address (to receive your license)

  Ready to begin? (y/n):
```

Type `y` and press Enter.

---

### Step 2: Fill Out the RTI Form

The wizard will open your web browser to RTI's website.

**What you'll see:**

- A form with the **"Free 60-day standard evaluation"** already selected
- Fields for your name, email, company, etc.

**What to do:**

1. Fill in your information
2. Complete the reCAPTCHA (click "I'm not a robot")
3. Click **Submit**

**Important:** After you submit, you'll see a download page. **Keep this page open!**

Go back to your terminal and press Enter.

---

### Step 3: Download the Software

The wizard will tell you which file to download based on your computer:

**Mac (Apple Silicon - M1/M2/M3):**
```
rti_connext_dds-7.X.X-pro-host-arm64Darwin.dmg
```

**Mac (Intel):**
```
rti_connext_dds-7.X.X-pro-host-x64Darwin.dmg
```

**Linux:**
```
rti_connext_dds-7.X.X-pro-host-x64Linux.run
```

Download the file and save it to your Downloads folder.

Press Enter in the terminal when done.

---

### Step 4: Install the Software

**On Mac:**
1. Find the `.dmg` file in your Downloads folder
2. Double-click to open it
3. Double-click the installer icon inside
4. Follow the installation steps
5. Use the default location (`/Applications/rti_connext_dds-7.X.X`)

**On Linux:**
```bash
cd ~/Downloads
chmod +x rti_connext_dds-*.run
./rti_connext_dds-*.run
```
Then follow the installer prompts.

Press Enter in the terminal when installation is complete.

---

### Step 5: Get Your License File

Check your email for a message from RTI. It will contain a file called:

```
rti_license.dat
```

**Tips:**
- It usually arrives within a few minutes
- Check your spam folder if you don't see it
- Download/save the `rti_license.dat` file to your Downloads folder

The wizard will find it automatically. If not, it will ask you where you saved it.

---

### Step 6: Configure Your Environment

The wizard will ask to add configuration to your shell (`.zshrc` or `.bashrc`).

Type `y` to allow it.

This sets up environment variables so GENESIS can find RTI Connext.

---

### Step 7: Verify Everything Works

The wizard runs verification checks:

```
  Running verification checks...

  ✓ NDDSHOME is set: /Applications/rti_connext_dds-7.3.0
  ✓ rtiddsspy found
  ✓ License file installed

  ╔════════════════════════════════════════════════════════════╗
  ║     SUCCESS! RTI Connext DDS is ready for GENESIS!         ║
  ╚════════════════════════════════════════════════════════════╝
```

---

## After Setup

### Install GENESIS

Open a **new terminal window** (important!), then:

```bash
./setup.sh
```

### Verify Anytime

To check your RTI setup anytime:

```bash
./rti_setup.sh --verify
```

---

## Troubleshooting

### "License file not found"

The license arrives via email from RTI. Check:
- Your inbox (from RTI)
- Your spam folder
- It may take a few minutes

Once you have it, run:
```bash
./rti_setup.sh --license
```

### "NDDSHOME is not set"

Your shell config wasn't loaded. Either:
- Open a new terminal window, OR
- Run: `source ~/.zshrc` (or `~/.bashrc`)

Then verify: `./rti_setup.sh --verify`

### "rtiddsspy not found"

The installation may not have completed. Try:
1. Run the installer again
2. Make sure you selected the default installation location

### Browser didn't open

If the browser doesn't open automatically, visit:

```
https://www.rti.com/get-connext?license_type=Standard%2030-day%20evaluation%20license
```

The 60-day evaluation will be pre-selected for you.

---

## Manual Setup (Advanced)

If you prefer to set things up manually:

### 1. Get License

Visit: https://www.rti.com/get-connext

Select "Free 60-day standard evaluation" and submit the form.

### 2. Download & Install

Download the host package for your platform and run the installer.

### 3. Set Environment Variables

Add to your `~/.zshrc` or `~/.bashrc`:

**Mac (Apple Silicon):**
```bash
export NDDSHOME="/Applications/rti_connext_dds-7.3.0"
export PATH="$NDDSHOME/bin:$PATH"
export DYLD_LIBRARY_PATH="$NDDSHOME/lib/arm64Darwin20clang12.0:$DYLD_LIBRARY_PATH"
```

**Mac (Intel):**
```bash
export NDDSHOME="/Applications/rti_connext_dds-7.3.0"
export PATH="$NDDSHOME/bin:$PATH"
export DYLD_LIBRARY_PATH="$NDDSHOME/lib/x64Darwin17clang9.0:$DYLD_LIBRARY_PATH"
```

**Linux:**
```bash
export NDDSHOME="$HOME/rti_connext_dds-7.3.0"
export PATH="$NDDSHOME/bin:$PATH"
export LD_LIBRARY_PATH="$NDDSHOME/lib/x64Linux4gcc7.3.0:$LD_LIBRARY_PATH"
```

### 4. Install License

Copy your license file:
```bash
cp ~/Downloads/rti_license.dat $NDDSHOME/
```

### 5. Verify

```bash
./rti_setup.sh --verify
```

---

## License Options

| License | Duration | Best For |
|---------|----------|----------|
| **60-Day Evaluation** | 60 days | Testing, prototyping, learning |
| Connext Express | Perpetual | Small projects (limited participants) |
| University Program | Perpetual | Academic research |

The wizard uses the 60-day evaluation, which has no limitations during the trial period.

Need to extend your license? Contact RTI at [support@rti.com](mailto:support@rti.com).

---

## Need Help?

- **GENESIS issues:** [genesis@rti.com](mailto:genesis@rti.com)
- **RTI Connext issues:** [RTI Support](https://www.rti.com/support)
- **Run the wizard again:** `./rti_setup.sh`

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
