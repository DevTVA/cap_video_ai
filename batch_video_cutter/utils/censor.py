"""Module quản lý kiểm duyệt và che từ nhạy cảm (Content Moderation Masking).

Thay thế các từ nhạy cảm (Bạo lực, Tình dục, Chửi thề, Ma túy, Vũ khí, v.v.)
bằng ký tự '*' theo phong cách Vowel / Core-Letter Masking (ví dụ: KILL -> KI*L, SEX -> SE*, FUCK -> F*CK)
cho Top Caption video và file tổng hợp all_clip_titles.txt nhằm đảm bảo an toàn chính sách nền tảng.
"""

import re
from typing import Dict, Pattern, List, Tuple


# Bộ từ điển kiểm duyệt chuẩn hóa cho Top Caption & External Titles
# Key: Regex pattern (có \b để tránh false-positive trên từ thông dụng)
# Value: Chuỗi thay thế có chứa ký tự '*'
CENSOR_DICTIONARY_RAW: Dict[str, str] = {
    # --- 1. Bạo lực, Giết chóc & Tội phạm (Violence, Crime & Injury) ---
    r"\bKILL\b": "KI*L",
    r"\bKILLS\b": "KI*LS",
    r"\bKILLED\b": "KI*LED",
    r"\bKILLING\b": "KI*LING",
    r"\bKILLER\b": "KI*LER",
    r"\bKILLERS\b": "KI*LERS",
    r"\bMURDER\b": "MU*DER",
    r"\bMURDERS\b": "MU*DERS",
    r"\bMURDERED\b": "MU*DERED",
    r"\bMURDERING\b": "MU*DERING",
    r"\bMURDERER\b": "MU*DERER",
    r"\bMURDERERS\b": "MU*DERERS",
    r"\bDEAD\b": "DE*D",
    r"\bDEATH\b": "DE*TH",
    r"\bDEATHS\b": "DE*THS",
    r"\bDIE\b": "D*E",
    r"\bDIES\b": "D*ES",
    r"\bDIED\b": "D*ED",
    r"\bDYING\b": "DY*NG",
    r"\bSUICIDE\b": "SU*CIDE",
    r"\bSUICIDAL\b": "SUIC*DAL",
    r"\bSHOOT\b": "SH*OT",
    r"\bSHOOTS\b": "SH*OTS",
    r"\bSHOT\b": "SH*T",
    r"\bSHOTS\b": "SH*TS",
    r"\bSHOOTING\b": "SH*OTING",
    r"\bSHOOTINGS\b": "SH*OTINGS",
    r"\bSHOOTER\b": "SH*OTER",
    r"\bSHOOTERS\b": "SH*OTERS",
    r"\bGUN\b": "G*N",
    r"\bGUNS\b": "G*NS",
    r"\bWEAPON\b": "WE*PON",
    r"\bWEAPONS\b": "WE*PONS",
    r"\bSTAB\b": "ST*B",
    r"\bSTABS\b": "ST*BS",
    r"\bSTABBED\b": "ST*BBED",
    r"\bSTABBING\b": "ST*BBING",
    r"\bBLOOD\b": "BL*OD",
    r"\bBLOODY\b": "BL*ODY",
    r"\bBLEED\b": "BL*ED",
    r"\bBLEEDING\b": "BLE*DING",
    r"\bCHOKE\b": "CH*KE",
    r"\bCHOKED\b": "CH*KED",
    r"\bCHOKING\b": "CH*KING",
    r"\bSTRANGLE\b": "STR*NGLE",
    r"\bSTRANGLED\b": "STR*NGLED",
    r"\bPOISON\b": "PO*SON",
    r"\bPOISONS\b": "PO*SONS",
    r"\bPOISONED\b": "PO*SONED",
    r"\bPOISONING\b": "PO*SONING",
    r"\bASSAULT\b": "ASS*ULT",
    r"\bASSAULTS\b": "ASS*ULTS",
    r"\bASSAULTED\b": "ASS*ULTED",
    r"\bASSAULTING\b": "ASS*ULTING",
    r"\bABUSE\b": "AB*SE",
    r"\bABUSES\b": "AB*SES",
    r"\bABUSED\b": "AB*SED",
    r"\bABUSING\b": "AB*SING",
    r"\bABUSIVE\b": "AB*SIVE",

    # --- 2. Tình dục, Người lớn & Xâm hại (Sexual & Adult Content) ---
    r"\bSEX\b": "SE*",
    r"\bSEXUAL\b": "SE*UAL",
    r"\bSEXY\b": "SE*Y",
    r"\bSEXING\b": "SE*ING",
    r"\bPORN\b": "PO*N",
    r"\bPORNO\b": "PO*NO",
    r"\bPORNOGRAPHY\b": "PO*NOGRAPHY",
    r"\bNUDE\b": "NU*E",
    r"\bNUDES\b": "NU*ES",
    r"\bNUDITY\b": "NU*ITY",
    r"\bNAKED\b": "NA*ED",
    r"\bRAPE\b": "RA*E",
    r"\bRAPES\b": "RA*ES",
    r"\bRAPED\b": "RA*ED",
    r"\bRAPING\b": "RA*ING",
    r"\bRAPIST\b": "RA*IST",
    r"\bRAPISTS\b": "RA*ISTS",
    r"\bPEDO\b": "PE*O",
    r"\bPEDOS\b": "PE*OS",
    r"\bPEDOPHILE\b": "PE*OPHILE",
    r"\bPEDOPHILES\b": "PE*OPHILES",
    r"\bMOLEST\b": "MO*EST",
    r"\bMOLESTS\b": "MO*ESTS",
    r"\bMOLESTED\b": "MO*ESTED",
    r"\bMOLESTING\b": "MO*ESTING",
    r"\bPENIS\b": "PE*IS",
    r"\bPENISES\b": "PE*ISES",
    r"\bVAGINA\b": "VA*INA",
    r"\bVAGINAS\b": "VA*INAS",
    r"\bBOOBS\b": "B*OBS",
    r"\bTITS\b": "T*TS",
    r"\bCOCK\b": "C*CK",
    r"\bCOCKS\b": "C*CKS",
    r"\bPUSSY\b": "PU*SY",
    r"\bPUSSIES\b": "PU*SIES",
    r"\bCUNT\b": "C*NT",
    r"\bCUNTS\b": "C*NTS",
    r"\bPROSTITUTE\b": "PROST*TUTE",
    r"\bPROSTITUTES\b": "PROST*TUTES",
    r"\bHOOKER\b": "HO*KER",
    r"\bHOOKERS\b": "HO*KERS",
    r"\bSLUT\b": "SL*T",
    r"\bSLUTS\b": "SL*TS",
    r"\bWHORE\b": "WH*RE",
    r"\bWHORES\b": "WH*RES",

    # --- 3. Chửi thề & Thô tục (Profanity & Vulgarity) ---
    r"\bFUCK\b": "F*CK",
    r"\bFUCKS\b": "F*CKS",
    r"\bFUCKING\b": "F*CKING",
    r"\bFUCKED\b": "F*CKED",
    r"\bFUCKER\b": "F*CKER",
    r"\bFUCKERS\b": "F*CKERS",
    r"\bMOTHERFUCKER\b": "MOTHERF*CKER",
    r"\bMOTHERFUCKERS\b": "MOTHERF*CKERS",
    r"\bSHIT\b": "SH*T",
    r"\bSHITS\b": "SH*TS",
    r"\bSHITTY\b": "SH*TTY",
    r"\bBULLSHIT\b": "BULLSH*T",
    r"\bBITCH\b": "BI*CH",
    r"\bBITCHES\b": "BI*CHES",
    r"\bBITCHING\b": "BI*CHING",
    r"\bASS\b": "A*S",
    r"\bASSHOLE\b": "A*SHOLE",
    r"\bASSHOLES\b": "A*SHOLES",
    r"\bDUMBASS\b": "DUMB*SS",
    r"\bBASTARD\b": "BA*TARD",
    r"\bBASTARDS\b": "BA*TARDS",
    r"\bDAMN\b": "D*MN",
    r"\bCRAP\b": "CR*P",

    # --- 4. Chất cấm & Nghiện ngập (Drugs & Substances) ---
    r"\bDRUG\b": "DR*G",
    r"\bDRUGS\b": "DR*GS",
    r"\bDRUGGED\b": "DR*GGED",
    r"\bDRUGGING\b": "DR*GGING",
    r"\bCOCAINE\b": "CO*AINE",
    r"\bHEROIN\b": "HE*OIN",
    r"\bWEED\b": "WE*D",
    r"\bMARIJUANA\b": "MARIJ*ANA",
    r"\bMETH\b": "M*TH",
    r"\bCRACK\b": "CR*CK",
    r"\bOPIOID\b": "OP*OID",
    r"\bOPIOIDS\b": "OP*OIDS",
    r"\bFENTANYL\b": "FENT*NYL",
    r"\bOVERDOSE\b": "OVERD*SE",
    r"\bOVERDOSES\b": "OVERD*SES",
    r"\bOVERDOSED\b": "OVERD*SED",
    r"\bADDICT\b": "ADD*CT",
    r"\bADDICTS\b": "ADD*CTS",
    r"\bADDICTION\b": "ADD*CTION",
    r"\bADDICTED\b": "ADD*CTED",

    # --- 5. Thù hận & Phân biệt (Hate & Discrimination) ---
    r"\bRACIST\b": "RA*IST",
    r"\bRACISTS\b": "RA*ISTS",
    r"\bRACISM\b": "RA*ISM",
    r"\bNAZI\b": "N*ZI",
    r"\bNAZIS\b": "N*ZIS",
    r"\bRETARD\b": "RET*RD",
    r"\bRETARDS\b": "RET*RDS",
    r"\bRETARDED\b": "RET*RDED",
    r"\bFAGGOT\b": "FA*GOT",
    r"\bFAGGOTS\b": "FA*GOTS",
    r"\bSLUR\b": "SL*R",
    r"\bSLURS\b": "SL*RS",
}

# Tối ưu hóa: Biên dịch sẵn danh sách regex để đạt hiệu năng xử lý tối đa
_COMPILED_PATTERNS: List[Tuple[Pattern, str]] = [
    (re.compile(p, re.IGNORECASE), repl)
    for p, repl in CENSOR_DICTIONARY_RAW.items()
]

# Export dictionary thô để tương thích ngược nếu cần
CENSOR_DICTIONARY = CENSOR_DICTIONARY_RAW


def censor_sensitive_words(text: str) -> str:
    """Thay thế các từ nhạy cảm trong văn bản bằng ký tự * theo phong cách Vowel/Core Masking.
    
    Bảo toàn tính an toàn chữ hoa/chữ thường và không gây false-positive trên từ thông dụng.
    Ví dụ:
        "HE KILLED HIS WIFE OVER DRUGS" -> "HE KI*LED HIS WIFE OVER DR*GS"
        "woman reveals shocking sex secrets" -> "woman reveals shocking se* secrets"
        "classic assessment of grass" -> "classic assessment of grass" (không đổi)
    """
    if not text:
        return ""
    
    result = text
    for pattern, replacement in _COMPILED_PATTERNS:
        # Hàm callback để giữ đúng case (UPPERCASE hoặc lowercase/TitleCase tương đối)
        def _replace_match(match: re.Match, rep: str = replacement) -> str:
            matched_str = match.group(0)
            if matched_str.isupper():
                return rep.upper()
            elif matched_str.islower():
                return rep.lower()
            elif matched_str.istitle():
                return rep.capitalize()
            return rep

        result = pattern.sub(lambda m, r=replacement: _replace_match(m, r), result)
    
    return result


def is_sensitive_text(text: str) -> bool:
    """Kiểm tra xem văn bản có chứa từ nhạy cảm nào trong từ điển hay không."""
    if not text:
        return False
    return any(pattern.search(text) is not None for pattern, _ in _COMPILED_PATTERNS)
