import sqlite3
import os
import numpy as np
import pandas as pd

class gnomAD_DB:
    
    def __init__(self, genodb_path):

        self.db_file = os.path.join(genodb_path, 'gnomad_db.sqlite3')
        
        self.columns = ["chrom", "pos", "ref", "alt", "AF", "AF_afr", "AF_eas", "AF_fin", "AF_nfe", "AF_asj", "AF_oth", "AF_popmax"]
        
        if not os.path.exists(self.db_file):
            if not os.path.exists(genodb_path):
                os.mkdir(genodb_path)
            self.create_table()
    
    
    
    def open_dbconn(self):
        return sqlite3.connect(self.db_file)
    
    
    def create_table(self):
        sql_create = """
        CREATE TABLE gnomad_db (
            chrom TEXT,
            pos INTEGER,
            ref TEXT,
            alt TEXT,
            AF REAL,
            AF_afr REAL,
            AF_eas REAL,
            AF_fin REAL,
            AF_nfe REAL,
            AF_asj REAL,
            AF_oth REAL,
            AF_popmax REAL,
            PRIMARY KEY (chrom, pos, ref, alt));
        """
        
        sql_index = """
        CREATE INDEX gnomad_db_chrom_pos_index 
        ON gnomad_db(chrom, pos);
        """
        
        with self.open_dbconn() as conn:
            c = conn.cursor()
            c.executescript(sql_create)
            c.executescript(sql_index)    
    
    def insert_variants(self, var_df: pd.DataFrame):
        assert np.array_equal(
            var_df.columns, 
            np.array(
                self.columns
            )
        ), "Columns are missing. The dataframe should contain: " + ", ".join(self.columns)
        
        
        
        
        ## sort and process var_df
        var_df = var_df.reindex(self.columns, axis=1)
        var_df = self._sanitize_variants(var_df)
        
        var_df = var_df[var_df.apply(lambda x: 
                                     len(x.ref) == (x.ref.count("A") + x.ref.count("T") + x.ref.count("C") + x.ref.count("G"))
                                     and
                                     len(x.alt) == (x.alt.count("A") + x.alt.count("T") + x.alt.count("C") + x.alt.count("G"))
                                                    ,axis=1)]
        
        rows = [tuple(x) for x in var_df.to_numpy()]
        
        sql_input = f"""
                    INSERT OR REPLACE INTO gnomad_db({", ".join(self.columns)})
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """
        with self.open_dbconn() as conn:
            c = conn.cursor()
            c.executemany(sql_input, rows)
    
    
    def _sanitize_variants(self, var_df: pd.DataFrame) -> pd.DataFrame:
        var_df["chrom"] = var_df.chrom.apply(lambda x: x.replace("chr", ""))
        return var_df
    
    def _pack_var_args(self, var: pd.Series) -> str:
        return f"'{var.chrom}', {var.pos}, '{var.ref}', '{var.alt}'"
    
    
    def get_maf_from_df(self, var_df: pd.DataFrame, query: str="AF") -> pd.Series:
        if var_df.empty:
            return var_df
        
        var_df = self._sanitize_variants(var_df)
        
        rows = [f"SELECT {self._pack_var_args(var)}" for _, var in var_df.iterrows()]
        
        rows = " UNION ALL ".join(rows)
        
        
        query = "tt.chrom, tt.pos, tt.ref, tt.alt, " + ", ".join(self.columns[4:]) if query == '*' else query
        
        sql_query = f"""
        WITH temp_table(chrom, pos, ref, alt) AS 
        ({rows})
        SELECT {query} FROM temp_table as tt
        LEFT JOIN gnomad_db AS gdb 
        ON tt.chrom = gdb.chrom AND tt.pos = gdb.pos AND tt.ref = gdb.ref AND tt.alt = gdb.alt;
        """
        
        with self.open_dbconn() as conn:
            return pd.read_sql_query(sql_query, conn)
    
    
    def get_maf_from_str(self, var: str, query: float="AF") -> float:
        # variant in form chrom:pos:ref>alt
        
        var = var.split(":")
        chrom = var[0].replace("chr", "")
        pos = var[1]
        ref = var[2].split(">")[0]
        alt = var[2].split(">")[1]
        
        var_df = pd.DataFrame({
                            "chrom": [chrom], 
                            "pos": [pos], 
                            "ref": [ref], 
                            "alt": [alt]})
        
        return self.get_maf_from_df(var_df, query).squeeze()